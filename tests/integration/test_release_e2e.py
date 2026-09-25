"""Release-level checks on the assembled build (service + B checks + workflow),
including provider outages. Runs fully offline."""
from pathlib import Path

import pytest

from boussla.config import FIXTURE_ROOT, get_settings
from boussla.contracts import Allocation, BousslaError, ErrorCode, Mode
from boussla.services import build_service
from boussla.workflow import WorkflowRunner

CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()
CLOSED_PORT = "http://127.0.0.1:9"  # nothing listens here: immediate connection failure


@pytest.fixture
def env(tmp_path, monkeypatch):
    for key, name in (("CASE_DB_PATH", "cases.sqlite"), ("CHECKPOINT_DB_PATH", "cp.sqlite"),
                      ("UPLOAD_DIR", "uploads"), ("EVENT_LOG_PATH", "events.jsonl")):
        monkeypatch.setenv(key, str(tmp_path / name))
    monkeypatch.setenv("LLM_PROVIDER", "manual")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def actors(svc):
    r = svc.registry.actors
    return r["DEMO-COMPANY-BAT"], r["DEMO-OFFICER"], r["DEMO-COMPANY-OTHER"]


def ver(svc):
    return svc.store.case_meta(CASE)["version"]


def code(fn):
    with pytest.raises(BousslaError) as e:
        fn()
    return e.value.code


def test_release_uses_lane_b_engine(env):
    svc = build_service()
    assert type(svc.checks).__name__ == "ChecksEngineV4"
    o = svc.get_case(actors(svc)[1], CASE)
    assert o.score.review_index == 40 and o.score.coverage_complete
    assert all(f.calculation_version.startswith("V4-") for f in o.findings)


def test_wrong_company_evidence_is_rejected(env):
    svc = build_service()
    co, off, other = actors(svc)
    d = svc.prepare_clarification(off, CASE, ver(svc))
    req = svc.publish_clarification(off, CASE, d.draft_id, ver(svc), "p")
    assert code(lambda: svc.upload_document(other, CASE, PDF, "x.pdf", "application/pdf", ver(svc), "u")) is ErrorCode.CROSS_COMPANY
    assert code(lambda: svc.submit_response(other, CASE, req.request.request_id, {"answers": {}}, ver(svc), "r")) is ErrorCode.CROSS_COMPANY
    # evidence id that is not a document of this case
    assert code(lambda: svc.submit_response(co, CASE, req.request.request_id, {"document_ids": ["DOC-OF-ANOTHER-CASE"]},
                                            ver(svc), "r2")) is ErrorCode.INVALID_EVIDENCE_REFERENCE
    # reallocation into a project the company does not own
    doc = svc.upload_document(co, CASE, PDF, "a.pdf", "application/pdf", ver(svc), "u2")
    resp = svc.submit_response(co, CASE, req.request.request_id, {
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001", "splits": {"P1": "1000", "P-OTHER": "1000"}}},
        ver(svc), "r3")
    assert code(lambda: svc.accept_evidence(off, CASE, resp.proposal_ids[0], ver(svc), "a")) is ErrorCode.CROSS_COMPANY
    assert [a.quantity for a in svc.store.facts(CASE, "allocation", Allocation)] == ["2000"]


def test_model_provider_unavailable_falls_back(env):
    env.setenv("LLM_PROVIDER", "openai")
    env.setenv("OPENAI_API_KEY", "sk-test-not-a-real-key")
    env.setenv("OPENAI_CHAT_MODEL", "gpt-4o-mini-2024-07-18")
    env.setenv("OPENAI_BASE_URL", CLOSED_PORT)
    get_settings.cache_clear()
    svc = build_service()
    runner = WorkflowRunner(svc)
    v = ver(svc)
    view = runner.run_analysis(actors(svc)[0], CASE, v)
    assert view.mode_by_node["planner"] is Mode.TEMPLATE and view.questions
    assert ver(svc) == v  # analysis does not mutate facts
    o = svc.get_case(actors(svc)[1], CASE)
    assert o.score.review_index == 40  # provider failure is not a finding


def test_tracing_unavailable_does_not_block_writes(env):
    env.setenv("LANGSMITH_TRACING", "true")
    env.setenv("LANGSMITH_API_KEY", "lsv2-test-not-a-real-key")
    env.setenv("LANGSMITH_ENDPOINT", CLOSED_PORT)
    get_settings.cache_clear()
    svc = build_service()
    runner = WorkflowRunner(svc, planner=None)
    co, off, _ = actors(svc)
    runner.run_analysis(co, CASE, ver(svc))
    d = svc.prepare_clarification(off, CASE, ver(svc))
    svc.publish_clarification(off, CASE, d.draft_id, ver(svc), "p")
    assert ver(svc) == 2


def test_restart_resume_decision_applies_once(env):
    svc = build_service()
    co, off, _ = actors(svc)
    d = svc.prepare_clarification(off, CASE, ver(svc))
    req = svc.publish_clarification(off, CASE, d.draft_id, ver(svc), "p")
    doc = svc.upload_document(co, CASE, PDF, "a.pdf", "application/pdf", ver(svc), "u")
    resp = svc.submit_response(co, CASE, req.request.request_id, {
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001", "splits": {"P1": "1000", "P2": "1000"}}},
        ver(svc), "r")
    v = ver(svc)
    r1 = WorkflowRunner(svc, planner=None)
    r1.open_decision(off, CASE, resp.proposal_ids[0], v)
    r1.close()
    svc2 = build_service()  # new process objects over the same files
    r2 = WorkflowRunner(svc2, planner=None)
    res = r2.decide(off, CASE, resp.proposal_ids[0], accept=True)
    assert res.new_version == v + 1 and res.score_after.review_index == 0
    assert r2.decide(off, CASE, resp.proposal_ids[0], accept=True).new_version == v + 1
    assert ver(svc2) == v + 1
    assert code(lambda: svc2.accept_evidence(off, CASE, resp.proposal_ids[0], v, "fresh-key")) is ErrorCode.STALE_REVISION
