"""Final sprint (lane A): judge round-1 regressions, automatic bounded clarification,
separate triage urgency, demo deadlines and the B/C integration contracts."""
from dataclasses import replace
from datetime import timedelta

import pytest
from starlette.testclient import TestClient

from boussla.config import FIXTURE_ROOT, Settings
from boussla.context.assistant import ContextConsistencyAssistant
from boussla.context.interpreter import OpenAIContextInterpreter
from boussla.contracts import (
    Allocation, BousslaError, ClarificationStatus, CompanyHistorySignal, ErrorCode, HistorySignalCode,
    Mode, ProposalStatus, RequestStatus,
)
from boussla.playbook import MAX_QUESTIONS_PER_ROUND, QUESTIONS
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import AUTO_ACTOR_ID, BousslaAppService
from boussla.store import CaseStore, utcnow
from boussla.triage import assess_triage, clarification_deadlines
from boussla.web.app import create_app

CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()
LINE = {"transaction_id": "TX-001", "line_id": "LINE-BUY-001"}
CONTEXT = {"project_id": "P1", "purpose_category": "CONSTRUCTION_PROJECT",
           "purpose_text": "Matériaux destinés au lot P1 et au lot P2.", "beneficiary_type": "Projet de maçonnerie"}


class Clock:
    def __init__(self):
        self.now = utcnow()

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make(tmp_path, clock):
    def build(**deps):
        root = tmp_path / f"s{len(list(tmp_path.iterdir()))}"  # one isolated store per service
        settings = Settings(case_db_path=root / "c.sqlite", upload_dir=root / "up")
        store = CaseStore(settings.case_db_path, settings.upload_dir)
        seed_demo_case(store)
        deps.setdefault("context_assistant", ContextConsistencyAssistant(OpenAIContextInterpreter(api_key=None)))
        return BousslaAppService(store, ActorRegistry.demo(), settings=settings, clock=clock, **deps)
    return build


@pytest.fixture
def svc(make):
    return make()


def co(svc):
    return svc.registry.actors["DEMO-COMPANY-BAT"]


def off(svc):
    return svc.registry.actors["DEMO-OFFICER"]


def ver(svc):
    return svc.store.case_meta(CASE)["version"]


def code(fn):
    with pytest.raises(BousslaError) as e:
        fn()
    return e.value.code


def authority(svc):
    """Everything authoritative: index, coverage, findings, canonical allocations."""
    ev = svc.evaluate(CASE)
    return (ev.score.review_index, ev.score.evidence_coverage,
            [(f.family, f.status, f.reason_code, f.quantity_difference) for f in ev.findings],
            [(a.target_project_id, a.quantity) for a in svc.store.facts(CASE, "allocation", Allocation)])


def officer_request(svc, key="publish"):
    draft = svc.prepare_clarification(off(svc), CASE, ver(svc))
    return svc.publish_clarification(off(svc), CASE, draft.draft_id, ver(svc), key).request.request_id


def upload(svc, key="upload"):
    return svc.upload_document(co(svc), CASE, PDF, "affectation.pdf", "application/pdf", ver(svc), key).document.document_id


def respond(svc, request_id, *, with_document=True, key="response", **allocation):
    docs = [upload(svc)] if with_document else []
    payload = {"document_ids": docs, "allocation": {**LINE, "splits": {"P1": "1000", "P2": "1000"}, **allocation}}
    return svc.submit_response(co(svc), CASE, request_id, payload, ver(svc), key)


# ---------------------------------------------------------------- judge round 1 regressions
def test_ljg001_documentless_declaration_is_never_accepted(svc):
    """JUDGE-008: allocation P1=1000/P2=1000 with document_ids=[] must not clear the index."""
    request_id = officer_request(svc)
    proposal = respond(svc, request_id, with_document=False).proposal_ids[0]
    before, v, revisions = authority(svc), ver(svc), len(svc.store.revisions(CASE))
    assert before[0] == 30  # provisional answer, not an accepted allocation
    assert code(lambda: svc.accept_evidence(off(svc), CASE, proposal, v, "accept")) is ErrorCode.INSUFFICIENT_INFORMATION
    assert authority(svc) == before and ver(svc) == v and len(svc.store.revisions(CASE)) == revisions
    assert all(not r.accepted_evidence_ids for r in svc.store.revisions(CASE))
    # The declaration can still be rejected (no canonical change) ...
    rejected = svc.reject_evidence(off(svc), CASE, proposal, v, "pièce manquante", "reject")
    assert rejected.outcome == "REJECTED" and rejected.score_after.review_index == 40
    # ... and a document-backed response is still accepted after human review.
    request_id = officer_request(svc, "publish-2")
    backed = respond(svc, request_id, key="response-2").proposal_ids[0]
    assert svc.accept_evidence(off(svc), CASE, backed, ver(svc), "accept-2").score_after.review_index == 0


@pytest.mark.parametrize("variant,allocation,expected", [
    ("wrong_unit", {"unit": "tonne"}, ErrorCode.INCOMPATIBLE_UNIT),
    ("wrong_currency", {"currency": "EUR"}, ErrorCode.INCOMPATIBLE_UNIT),
    ("tnd_currency", {"currency": "TND"}, ErrorCode.INCOMPATIBLE_UNIT),
    ("unknown_property", {"note": "x"}, ErrorCode.INVALID_INPUT),
    ("infinity", {"splits": {"P1": "Infinity"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("nan", {"splits": {"P1": "NaN"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("huge_decimal", {"splits": {"P1": "1e999999999"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("huge_integer", {"splits": {"P1": "9" * 400}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("negative", {"splits": {"P1": "-1", "P2": "2001"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("float", {"splits": {"P1": 1000.0, "P2": "1000"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("boolean", {"splits": {"P1": True, "P2": "1000"}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("nested", {"splits": {"P1": {"q": "1"}}}, ErrorCode.INSUFFICIENT_INFORMATION),
    ("empty_splits", {"splits": {}}, ErrorCode.INSUFFICIENT_INFORMATION),
])
def test_ljg002_ljg003_tampered_allocations_are_typed_rejections(svc, variant, allocation, expected):
    """JUDGE-028: unit/currency never silently dropped; non-finite/extreme values typed."""
    request_id = officer_request(svc)
    doc = upload(svc)
    before, v = authority(svc), ver(svc)
    payload = {"document_ids": [doc], "allocation": {**LINE, "splits": {"P1": "1000", "P2": "1000"}, **allocation}}
    assert code(lambda: svc.submit_response(co(svc), CASE, request_id, payload, v, "response")) is expected
    assert authority(svc) == before and ver(svc) == v


def test_matching_unit_is_accepted_and_quantities_are_canonical(svc):
    request_id = officer_request(svc)
    unit = svc._facts(CASE)["invoice_observation"][0].lines[0].unit
    proposal_id = respond(svc, request_id, unit=f" {unit} ", splits={"P1": "1000.000", "P2": "01000"}).proposal_ids[0]
    proposal = next(p for p in svc.get_case(off(svc), CASE).proposals if p.proposal_id == proposal_id)
    assert {c.target_project_id: c.new_quantity for c in proposal.changes} == {"P1": "1000", "P2": "1000"}
    assert svc.accept_evidence(off(svc), CASE, proposal_id, ver(svc), "a").score_after.review_index == 0


def test_unexpected_response_property_is_rejected(svc):
    request_id = officer_request(svc)
    v = ver(svc)
    assert code(lambda: svc.submit_response(co(svc), CASE, request_id, {"answers": {}, "review_index": 0}, v, "r")) \
        is ErrorCode.INVALID_INPUT
    assert code(lambda: svc.submit_response(co(svc), CASE, request_id, {"answers": ["x"]}, v, "r2")) \
        is ErrorCode.INVALID_INPUT
    assert ver(svc) == v


@pytest.mark.parametrize("extra,expected", [
    ({"review_index": 0, "arbitrary_property": "not-in-contract"}, ErrorCode.INVALID_INPUT),
    ({"purpose_text": {"nested": "x"}}, ErrorCode.INVALID_INPUT),
    ({"stage": ["a"]}, ErrorCode.INVALID_INPUT),
    ({"reported_stock_qty": "1e999999999"}, ErrorCode.INSUFFICIENT_INFORMATION),
    ({"reported_stock_qty": "Infinity"}, ErrorCode.INSUFFICIENT_INFORMATION),
])
def test_ljg004_unexpected_context_properties_are_rejected(svc, extra, expected):
    """JUDGE-037: extra properties are a typed rejection, not a silent drop."""
    before, v = authority(svc), ver(svc)
    payload = {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "synthetic", **extra}
    assert code(lambda: svc.submit_context(co(svc), CASE, payload, v, "ctx")) is expected
    assert authority(svc) == before and ver(svc) == v


def test_http_maps_new_rejections_to_typed_400(svc):
    client = TestClient(create_app(svc))
    h = {"X-Boussla-Demo-Role": "COMPANY", "Idempotency-Key": "k-1"}
    r = client.post(f"/api/cases/{CASE}/context", headers=h, json={"expected_version": ver(svc), "context": {
        "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "x", "arbitrary_property": 1}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_INPUT"
    request_id = officer_request(svc)
    r = client.post(f"/api/cases/{CASE}/responses/{request_id}", headers={**h, "Idempotency-Key": "k-2"}, json={
        "expected_version": ver(svc), "response": {"allocation": {**LINE, "currency": "EUR", "splits": {"P1": "1"}}}})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INCOMPATIBLE_UNIT"


# ---------------------------------------------------------------- automatic clarification
def inbox(svc):
    return svc.get_case(co(svc), CASE).inbox


def test_company_context_publishes_one_neutral_automatic_request(svc):
    v = ver(svc)
    view = svc.submit_context(co(svc), CASE, CONTEXT, v, "ctx")
    assert view.case_version == v + 1  # same revision as the submission, no extra version
    [req] = view.inbox
    assert req.request.origin == "AUTOMATIC" and req.request.approved_by is None
    assert req.request.status is RequestStatus.PUBLISHED_IN_DEMO and req.request.request_id.startswith("REQ-AUTO-")
    assert 0 < len(req.questions) <= MAX_QUESTIONS_PER_ROUND
    assert all(QUESTIONS[q.question_id].text_fr == q.text_fr
               and QUESTIONS[q.question_id].answer_kind == q.answer_kind
               and QUESTIONS[q.question_id].choices == q.choices for q in req.questions)
    assert all(q.related_fact_ids == ("TX-001",) for q in req.questions
               if q.question_id in {"Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"})
    assert req.request.target_kind == "DEMO_SERVICE_TARGET"
    text = (req.text_fr + " ".join(q.text_fr for q in req.questions)).lower()
    assert not any(w in text for w in ("fraude", "risque", "sanction", "infraction", "pénal"))
    assert "ni une accusation ni une décision" in req.text_fr
    [event] = [e for e in svc.store.events(CASE) if e.kind == "AUTO_CLARIFICATION_PUBLISHED"]
    assert event.actor_id == AUTO_ACTOR_ID and event.case_version == v + 1
    assert "automatique" in svc.store.revisions(CASE)[-1].reason
    assert svc.evaluate(CASE).score.review_index == 40  # a question is never a finding


def test_automatic_request_is_idempotent_and_never_duplicated(svc):
    v = ver(svc)
    svc.submit_context(co(svc), CASE, CONTEXT, v, "ctx")
    replay = svc.submit_context(co(svc), CASE, CONTEXT, v, "ctx")  # identical retry
    assert replay.case_version == v + 1 and len(replay.inbox) == 1
    svc.submit_context(co(svc), CASE, {**CONTEXT, "purpose_text": "Précision"}, ver(svc), "ctx-2")
    upload(svc)  # further company submissions while a request is pending
    assert len(inbox(svc)) == 1
    assert sum(e.kind == "AUTO_CLARIFICATION_PUBLISHED" for e in svc.store.events(CASE)) == 1


def test_company_upload_triggers_but_officer_upload_does_not(make):
    svc = make()
    svc.upload_document(off(svc), CASE, PDF, "a.pdf", "application/pdf", ver(svc), "officer-upload")
    assert not svc.get_case(off(svc), CASE).requests
    svc2 = make()
    other = (FIXTURE_ROOT / "documents" / "01_buyer_invoice.pdf").read_bytes()
    svc2.upload_document(co(svc2), CASE, other, "b.pdf", "application/pdf", ver(svc2), "company-upload")
    [req] = svc2.get_case(off(svc2), CASE).requests
    assert req.request.origin == "AUTOMATIC"


def test_full_40_to_0_without_officer_preparing_a_request(svc):
    svc.submit_context(co(svc), CASE, CONTEXT, ver(svc), "ctx")
    [req] = inbox(svc)
    assert "Q-PROJECT-ALLOCATION" in req.request.question_ids
    response = respond(svc, req.request.request_id)
    officer = svc.get_case(off(svc), CASE)
    assert officer.score.review_index == 20 and len(officer.requests) == 1
    assert officer.requests[0].request.status is RequestStatus.RESPONDED
    result = svc.accept_evidence(off(svc), CASE, response.proposal_ids[0], ver(svc), "accept")  # human decision
    assert (result.score_before.review_index, result.score_after.review_index) == (20, 0)
    assert len(svc.get_case(off(svc), CASE).requests) == 1  # nothing re-asked after acceptance


def test_context_mismatch_flow_is_bounded_by_configured_rounds(svc):
    mismatch = {**CONTEXT, "declared_horizon": "SHORT_HORIZON", "stage": "Gros œuvre",
                "planned_start": "2027-01-01", "planned_end": "2028-06-30"}
    svc.submit_context(co(svc), CASE, mismatch, ver(svc), "ctx")
    [first] = inbox(svc)
    assert first.request.question_ids[0] == "Q-HORIZON-CONFIRM"  # contradiction first, global cap 3
    assert svc.get_case(co(svc), CASE).context_assessment.consistency_status == "NEEDS_CLARIFICATION"
    svc.submit_response(co(svc), CASE, first.request.request_id,
                        {"answers": {"Q-HORIZON-CONFIRM": "LONGER_HORIZON"}}, ver(svc), "answer")
    assert svc.get_case(co(svc), CASE).context_assessment.consistency_status == "CONSISTENT"
    requests = svc.get_case(off(svc), CASE).requests
    assert len(requests) <= svc.settings.max_question_rounds
    asked = [q for r in requests for q in r.request.question_ids]
    assert len(asked) == len(set(asked))  # never re-asked automatically
    for r in [r for r in requests if r.request.status is RequestStatus.PUBLISHED_IN_DEMO]:
        svc.submit_response(co(svc), CASE, r.request.request_id, {"answers": {}}, ver(svc), f"r-{r.request.request_id}")
    svc.submit_context(co(svc), CASE, {**CONTEXT, "purpose_text": "Encore"}, ver(svc), "ctx-3")
    assert len(svc.get_case(off(svc), CASE).requests) == svc.settings.max_question_rounds  # budget exhausted
    assert svc.evaluate(CASE).score.review_index == 40


def test_no_automatic_request_while_a_proposal_awaits_the_officer(svc):
    request_id = officer_request(svc)
    respond(svc, request_id)
    svc.submit_context(co(svc), CASE, CONTEXT, ver(svc), "ctx")
    assert len(svc.get_case(off(svc), CASE).requests) == 1


# ---------------------------------------------------------------- triage and deadlines
def test_unanswered_request_changes_triage_only(svc, clock):
    initial = svc.get_case(off(svc), CASE)
    assert initial.triage.triage_priority == 40 and initial.triage.reason_codes == ("REVIEW_FINDING_PRESENT",)
    svc.submit_context(co(svc), CASE, CONTEXT, ver(svc), "ctx")
    pending = svc.get_case(off(svc), CASE)
    assert pending.triage.triage_priority == 50 and "CLARIFICATION_PENDING" in pending.triage.reason_codes
    assert not pending.clarification_deadlines[0].overdue
    before, v, events = authority(svc), ver(svc), len(svc.store.events(CASE))

    clock.now += timedelta(days=10)  # demo target is 7 days: 3 days overdue
    late = svc.get_case(off(svc), CASE)
    [deadline] = late.clarification_deadlines
    assert deadline.overdue and deadline.overdue_days == 3 and deadline.target_kind == "DEMO_SERVICE_TARGET"
    assert late.triage.triage_priority == 60
    assert late.triage.reason_codes == ("REVIEW_FINDING_PRESENT", "CLARIFICATION_PENDING", "CLARIFICATION_OVERDUE")
    assert late.score.review_index == 40 and late.score.clarification_status is ClarificationStatus.FOLLOW_UP_DUE
    assert late.findings == svc.get_case(off(svc), CASE).findings
    # Reading never writes: no new version, event, finding or score change.
    assert authority(svc) == before and ver(svc) == v and len(svc.store.events(CASE)) == events
    [item] = svc.list_queue(off(svc), None, 10).items
    assert (item.review_index, item.triage_priority) == (40, 60) and "CLARIFICATION_OVERDUE" in item.triage_reason_codes
    company = svc.get_case(co(svc), CASE).model_dump()
    assert not {"triage", "score", "clarification_deadlines", "history_signals", "investigator_brief"} & company.keys()


def test_proposal_awaiting_decision_keeps_triage_separate_from_provisional_index(svc):
    respond(svc, officer_request(svc))
    view = svc.get_case(off(svc), CASE)
    assert "EVIDENCE_AWAITING_OFFICER_DECISION" in view.triage.reason_codes
    assert view.score.review_index == 20 and view.triage.triage_priority == 50
    assert view.score.raw_review_index == 40
    assert view.triage.components["REVIEW_INDEX_BASE"] == 40


def signal(code, company="DEMO-BAT", sid="S"):
    return CompanyHistorySignal(signal_id=sid, company_id=company, reason_code=code, period="2025-09/2025-10",
                                metric="m", observed_value="2", explanation_fr="observation synthétique neutre",
                                method="SYNTHETIC_HISTORY_V1", mode=Mode.LIVE)


def test_triage_formula_is_transparent_and_capped(svc):
    now = utcnow()
    ev = svc.evaluate(CASE)
    signals = tuple(signal(c, sid=c.value) for c in HistorySignalCode)
    t = assess_triage(case_id=CASE, case_version=1, review_index=95, findings=ev.findings, deadlines=(),
                      proposals=(), history_signals=signals, now=now)
    assert t.triage_priority == 100 and t.review_index == 95 and t.not_fraud_probability
    assert t.components == {"REVIEW_INDEX_BASE": 95, "REVIEW_FINDING_PRESENT": 0, "ACTIVITY_GAP_NEEDS_REVIEW": 10,
                            "HISTORICAL_DATA_GAP_NEEDS_REVIEW": 10, "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW": 10,
                            "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW": 5}
    quiet = assess_triage(case_id=CASE, case_version=1, review_index=0, findings=(), deadlines=(), proposals=(),
                          history_signals=(signal(HistorySignalCode.NO_SIGNIFICANT_CHANGE),), now=now)
    assert (quiet.triage_priority, quiet.reason_codes) == (0, ())
    assert clarification_deadlines((), now) == ()


# ---------------------------------------------------------------- lane B / lane C wiring
class Signals:
    def __init__(self, fail=False):
        self.fail = fail

    def signals(self, company_id, as_of):
        if self.fail:
            raise RuntimeError("history source down")
        return [signal(HistorySignalCode.ACTIVITY_GAP, company_id, "SIG-1"),
                signal(HistorySignalCode.REPEATED_INVOICE_CONFLICT, "DEMO-OTHER", "SIG-X")]


def test_history_signals_raise_triage_only_and_failures_are_nonfatal(make):
    svc = make(history_signal_provider=Signals())
    view = svc.get_case(off(svc), CASE)
    assert [s.signal_id for s in view.history_signals] == ["SIG-1"]  # other company's signal filtered
    assert view.triage.reason_codes == ("REVIEW_FINDING_PRESENT", "ACTIVITY_GAP_NEEDS_REVIEW")
    assert view.triage.triage_priority == 50 and view.score.review_index == 40
    assert view.mode_by_node["history"] is Mode.LIVE
    broken = make(history_signal_provider=Signals(fail=True))
    view = broken.get_case(off(broken), CASE)
    assert view.mode_by_node["history"] is Mode.ERROR and view.triage.triage_priority == 40


class Selector:
    """Stands in for the OpenAI selector: returns IDs only."""

    def __init__(self, hypotheses=("SECOND_PROJECT_ALLOCATION",), questions=("Q-PROJECT-ALLOCATION",), fail=False):
        self.value, self.fail, self.calls = (tuple(hypotheses), tuple(questions)), fail, 0

    def select(self, data, eligible_hypotheses, eligible_questions):
        self.calls += 1
        if self.fail:
            raise TimeoutError
        return self.value


class Rogue:
    """An investigator that ignores the catalogue: the service must drop its brief."""

    def assess(self, data, audience):
        from boussla.investigator import InvestigatorAssistant
        result = InvestigatorAssistant().assess(data, audience=audience)
        hyp = result.brief.top_hypotheses[0].__class__(
            hypothesis_id="COMPANY_IS_FRAUDULENT", status=result.brief.top_hypotheses[0].status,
            supporting_refs=(), contradicting_refs=(), missing_evidence=(), why_it_matters_fr="x")
        return result.__class__(replace(result.brief, top_hypotheses=(hyp,)), result.mode)


@pytest.mark.parametrize("selector,present,mode,first", [
    (Selector(), True, Mode.LIVE, "SECOND_PROJECT_ALLOCATION"),
    (Selector(hypotheses=("NOT_IN_CATALOGUE",)), True, Mode.TEMPLATE, "SECOND_PROJECT_ALLOCATION"),
    (Selector(questions=("Q-FREE-TEXT",)), True, Mode.TEMPLATE, "SECOND_PROJECT_ALLOCATION"),
    (Selector(fail=True), True, Mode.TEMPLATE, "SECOND_PROJECT_ALLOCATION"),  # model outage -> template
])
def test_investigator_brief_is_bounded_officer_only_and_nonfatal(make, selector, present, mode, first):
    from boussla.investigator import InvestigatorAssistant
    svc = make(investigator=InvestigatorAssistant(selector))
    view = svc.get_case(off(svc), CASE)
    assert (view.investigator_brief is not None) is present and view.mode_by_node["investigator"] is mode
    assert view.score.review_index == 40 and view.triage.triage_priority == 40
    if present:
        brief = view.investigator_brief
        assert brief.top_hypotheses[0].hypothesis_id == first and len(brief.top_hypotheses) <= 5
        assert brief.label_fr == "Analyse assistée BOUSSLA" and brief.authoritative is False
        assert brief.disclaimer_fr == "L'analyse assistée ne modifie pas l'indice de revue ni les faits du dossier."
        assert set(brief.questions_proposed) <= set(QUESTIONS) and len(brief.questions_proposed) <= 3
        assert all(h.name_fr and "fraude" not in h.name_fr.lower() for h in brief.top_hypotheses)
    assert "investigator_brief" not in svc.get_case(co(svc), CASE).model_dump()


def test_investigator_is_cached_per_version_and_rogue_output_is_dropped(make):
    from boussla.investigator import InvestigatorAssistant
    selector = Selector()
    svc = make(investigator=InvestigatorAssistant(selector))
    for _ in range(3):
        svc.get_case(off(svc), CASE)
    assert selector.calls == 1
    svc.submit_context(co(svc), CASE, CONTEXT, ver(svc), "ctx")  # new version -> recomputed once
    svc.get_case(off(svc), CASE)
    assert selector.calls == 2
    rogue = make(investigator=Rogue())
    view = rogue.get_case(off(rogue), CASE)  # rogue output dropped; deterministic template shown instead
    assert view.mode_by_node["investigator"] is Mode.TEMPLATE
    assert "COMPANY_IS_FRAUDULENT" not in view.investigator_brief.model_dump_json()
    assert make().get_case(off(svc), CASE).mode_by_node["investigator"] is Mode.NOT_RUN
