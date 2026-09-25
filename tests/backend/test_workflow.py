"""LangGraph workflow: interrupts, restart/resume, no repeated side effects."""
import pytest

from boussla.config import FIXTURE_ROOT, Settings
from boussla.contracts import AnalysisStatus, BousslaError, ErrorCode, Mode, ProposalStatus
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import BousslaAppService
from boussla.store import CaseStore
from boussla.workflow import WorkflowRunner

CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


def fake_planner(ev, facts, allowed):
    return [q for q in ("Q-PROJECT-ALLOCATION", "NOT-ALLOWED") if q in allowed or q == "NOT-ALLOWED"], Mode.LIVE


@pytest.fixture
def env(tmp_path):
    settings = Settings(case_db_path=tmp_path / "c.sqlite", upload_dir=tmp_path / "up",
                        checkpoint_db_path=tmp_path / "cp.sqlite", event_log_path=tmp_path / "ev.jsonl")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    registry = ActorRegistry.demo()

    def make(planner=fake_planner):
        svc = BousslaAppService(store, registry, settings=settings)
        return WorkflowRunner(svc, settings.checkpoint_db_path, planner=planner)
    return make, registry.actors


def ver(runner):
    return runner.service.store.case_meta(CASE)["version"]


def test_company_analysis_interrupts_and_resumes_after_restart(env):
    make, actors = env
    co = actors["DEMO-COMPANY-BAT"]
    r1 = make()
    view = r1.run_analysis(co, CASE, ver(r1))
    assert view.status is AnalysisStatus.AWAITING_COMPANY_ANSWER
    assert [q.question_id for q in view.questions] == ["Q-PROJECT-ALLOCATION"]  # invalid ID filtered
    assert view.mode_by_node["planner"] is Mode.LIVE and view.findings == ()
    r1.close()
    r2 = make()  # "app restart": new process objects, same checkpoint file
    after = r2.submit_answers(co, CASE, {"Q-PROJECT-ALLOCATION": "1000 P1 / 1000 P2"})
    assert "Q-PROJECT-ALLOCATION" not in {q.question_id for q in after.questions}
    answers = [c for c in r2.service.store.facts(CASE, "context_claim", type(r2.service.get_case(co, CASE).context_claims[0]))
               if c.purpose_text.startswith("[Q-PROJECT-ALLOCATION]")]
    assert len(answers) == 1


def test_planner_failure_falls_back_to_template(env):
    make, actors = env

    def broken(*_):
        raise TimeoutError("provider down")
    r = make(planner=broken)
    view = r.run_analysis(actors["DEMO-COMPANY-BAT"], CASE, ver(r))
    assert view.mode_by_node["planner"] is Mode.TEMPLATE and view.questions


def test_wrong_company_cannot_start_or_resume(env):
    make, actors = env
    r = make()
    r.run_analysis(actors["DEMO-COMPANY-BAT"], CASE, ver(r))
    for fn in (lambda: r.run_analysis(actors["DEMO-COMPANY-OTHER"], CASE, ver(r)),
               lambda: r.submit_answers(actors["DEMO-COMPANY-OTHER"], CASE, {"Q-PROJECT-ALLOCATION": "x"})):
        with pytest.raises(BousslaError) as e:
            fn()
        assert e.value.code is ErrorCode.CROSS_COMPANY


def _proposal(r, actors):
    co, off = actors["DEMO-COMPANY-BAT"], actors["DEMO-OFFICER"]
    svc = r.service
    d = svc.prepare_clarification(off, CASE, ver(r))
    req = svc.publish_clarification(off, CASE, d.draft_id, ver(r), "p")
    doc = svc.upload_document(co, CASE, PDF, "p2.pdf", "application/pdf", ver(r), "u")
    return svc.submit_response(co, CASE, req.request.request_id, {
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001", "splits": {"P1": "1000", "P2": "1000"}}},
        ver(r), "resp").proposal_ids[0]


def test_decision_resume_after_restart_applies_once(env):
    make, actors = env
    off = actors["DEMO-OFFICER"]
    r1 = make()
    pid = _proposal(r1, actors)
    v = ver(r1)
    assert r1.open_decision(off, CASE, pid, v)["awaiting_decision"]
    r1.close()
    r2 = make()
    res = r2.decide(off, CASE, pid, accept=True)
    assert res.outcome == "ACCEPTED" and res.new_version == v + 1 and res.score_after.review_index == 0
    again = r2.decide(off, CASE, pid, accept=True)  # repeated click / resumed thread
    assert again.new_version == res.new_version and ver(r2) == v + 1
    with pytest.raises(BousslaError):
        r2.decide(off, CASE, pid, accept=False)
    assert r2.service.get_case(off, CASE).proposals[0].status is ProposalStatus.ACCEPTED


def test_commit_after_crash_replays_receipt(env):
    """Service committed but checkpoint did not record it: resume must not re-apply."""
    make, actors = env
    off = actors["DEMO-OFFICER"]
    r = make()
    pid = _proposal(r, actors)
    v = ver(r)
    r.open_decision(off, CASE, pid, v)
    first = r.service.accept_evidence(off, CASE, pid, v, f"wf:decision:{CASE}:{pid}:v{v}")
    res = r.decide(off, CASE, pid, accept=True)
    assert res.replayed and res.new_version == first.new_version and ver(r) == v + 1


def test_company_cannot_open_decision(env):
    make, actors = env
    r = make()
    pid = _proposal(r, actors)
    with pytest.raises(BousslaError) as e:
        r.open_decision(actors["DEMO-COMPANY-BAT"], CASE, pid, ver(r))
    assert e.value.code is ErrorCode.FORBIDDEN
