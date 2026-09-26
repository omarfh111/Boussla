"""Context consistency through the real service: clarification only, never scoring.
Offline: C's real OpenAIContextInterpreter over an httpx MockTransport."""
import json
import re

import httpx
import pytest

from boussla.context.assistant import ContextConsistencyAssistant
from boussla.context.interpreter import OpenAIContextInterpreter
from boussla.contracts import AnalysisStatus, BousslaError, ContextClaim, ErrorCode, HorizonBucket, Mode
from boussla.services import BousslaAppService, build_service
from boussla.workflow import WorkflowRunner

CASE = "CASE-BRICKS-001"
PURPOSE = "Construction d'un dépôt logistique prévue sur environ dix-huit mois"
LONG = {"planned_start": "2027-01-01", "planned_end": "2028-06-30"}  # 546 days
FORBIDDEN = ("CASE-", "DEMO-BAT", "DEMO-MF", "Bâtisseur", "4760000", "FAC-DEMO", "CLIENT_PROJECT", "Client du chantier")


class ModelStub:
    """Mocked Responses API for the context interpreter; records every request body."""

    def __init__(self, category="OTHER_OR_UNKNOWN", horizon="UNKNOWN", explicit=None, spans=(), status=200):
        self.answer = {"suggested_purpose_category": category, "suggested_horizon": horizon,
                       "explicit_duration_text": explicit, "supporting_spans": list(spans), "ambiguities": []}
        self.status, self.requests = status, []

    def __call__(self, request):
        self.requests.append(json.loads(request.content))
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(200, json={"status": "completed", "model": "gpt-test", "output": [
            {"content": [{"type": "output_text", "text": json.dumps(self.answer)}]}]})


def service(stub=None):
    base = build_service()
    interpreter = OpenAIContextInterpreter(api_key="test-only" if stub else None, model="gpt-test",
                                           client=httpx.Client(transport=httpx.MockTransport(stub or ModelStub())))
    return BousslaAppService(base.store, base.registry, settings=base.settings,
                             context_assistant=ContextConsistencyAssistant(interpreter))


def actors(svc):
    return svc.registry.actors["DEMO-COMPANY-BAT"], svc.registry.actors["DEMO-OFFICER"]


def ver(svc):
    return svc.store.case_meta(CASE)["version"]


def deterministic(svc):
    """Everything scoring-related, independent of the case version counter."""
    o = svc.get_case(actors(svc)[1], CASE)
    def strip(items):  # finding/hypothesis ids embed the version counter; content must be identical
        return [re.sub(r":v\d+", ":v", i.model_copy(update={"case_version": 0}).model_dump_json()) for i in items]
    s = o.score
    return (s.review_index, s.evidence_coverage, s.coverage_complete, s.contributions, s.tested_families,
            s.unknown_families, s.unresolved_distinct_transactions, strip(o.findings), strip(o.hypotheses),
            [re.sub(r":v\d+", ":v", sc.model_dump_json()) for sc in o.scenarios])


def declare(svc, key, **fields):
    payload = {"project_id": "P1", "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": PURPOSE,
               "beneficiary_type": "Maître d'ouvrage privé", **fields}
    return svc.submit_context(actors(svc)[0], CASE, payload, ver(svc), key)


def company_questions(svc):
    return [q.question_id for q in svc.start_analysis(actors(svc)[0], CASE, ver(svc)).questions]


def test_seed_brick_case_is_consistent_and_keeps_planner_questions():
    svc = service()
    ctx = svc.get_case(actors(svc)[0], CASE).context_assessment
    assert ctx.consistency_status == "CONSISTENT" and ctx.duration_days == 90
    assert ctx.calculated_horizon is HorizonBucket.SHORT_HORIZON and ctx.declared_horizon is HorizonBucket.UNKNOWN
    assert company_questions(svc) == ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]
    assert deterministic(svc)[0] == 40


def test_A_declared_short_dates_longer_needs_clarification_score_unchanged():
    svc = service()
    before = deterministic(svc)
    view = declare(svc, "a", declared_horizon="SHORT_HORIZON", stage="Gros œuvre", **LONG)
    ctx = view.context_assessment
    assert (ctx.duration_days, ctx.calculated_horizon, ctx.declared_horizon) == (546, HorizonBucket.LONGER_HORIZON,
                                                                                  HorizonBucket.SHORT_HORIZON)
    assert ctx.consistency_status == "NEEDS_CLARIFICATION" and "DECLARED_HORIZON_DATE_CONFLICT" in ctx.reason_codes
    assert company_questions(svc)[0] == "Q-HORIZON-CONFIRM"
    assert deterministic(svc) == before


def test_B_model_longer_company_short_no_dates_score_unchanged():
    stub = ModelStub("CONSTRUCTION_PROJECT", "LONGER_HORIZON", "environ dix-huit mois", ["dépôt logistique"])
    svc = service(stub)
    before = deterministic(svc)
    ctx = declare(svc, "b", declared_horizon="SHORT_HORIZON", stage="Études").context_assessment
    assert ctx.interpreted_horizon is HorizonBucket.LONGER_HORIZON and ctx.interpretation_mode is Mode.LIVE
    assert ctx.calculated_horizon is HorizonBucket.UNKNOWN and ctx.duration_days is None
    assert "DECLARED_HORIZON_TEXT_CONFLICT" in ctx.reason_codes and ctx.consistency_status == "NEEDS_CLARIFICATION"
    assert set(ctx.supporting_spans) <= {"dépôt logistique", "environ dix-huit mois"}
    assert "Q-HORIZON-CONFIRM" in company_questions(svc)
    assert deterministic(svc) == before


def test_C_longer_project_missing_stage_asks_stage_score_unchanged():
    svc = service()
    before = deterministic(svc)
    ctx = declare(svc, "c", declared_horizon="LONGER_HORIZON", **LONG).context_assessment
    assert ctx.reason_codes == ("LONG_HORIZON_STAGE_MISSING",) and ctx.consistency_status == "NEEDS_CLARIFICATION"
    assert ctx.recommended_question_ids == ("Q-PROJECT-STAGE",)
    # Priority 3 (missing context) yields to the 3 finding-planner questions in round 1 ...
    first = svc.start_analysis(actors(svc)[0], CASE, ver(svc))
    assert [q.question_id for q in first.questions] == ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]
    after = svc.answer_questions(actors(svc)[0], CASE, first.analysis_id,
                                 {q.question_id: "réponse" for q in first.questions}, ver(svc), "round-1")
    # ... and is asked in round 2 (answered IDs are not repeated).
    assert after.status is AnalysisStatus.AWAITING_COMPANY_ANSWER
    assert [q.question_id for q in after.questions] == ["Q-PROJECT-STAGE"]
    assert deterministic(svc) == before


def test_D_complete_longer_project_adds_no_questions_score_unchanged():
    svc = service()
    before = deterministic(svc)
    ctx = declare(svc, "d", declared_horizon="LONGER_HORIZON", stage="Gros œuvre", **LONG).context_assessment
    assert ctx.consistency_status == "CONSISTENT" and ctx.reason_codes == ()
    assert company_questions(svc) == ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]  # planner only
    assert deterministic(svc) == before


@pytest.mark.parametrize("stub", [ModelStub(status=503), ModelStub(status=401)])
def test_E_provider_unavailable_still_detects_date_conflict(stub):
    svc = service(stub)
    before = deterministic(svc)
    ctx = declare(svc, "e", declared_horizon="SHORT_HORIZON", stage="Gros œuvre", **LONG).context_assessment
    assert ctx.interpretation_mode is Mode.TEMPLATE and ctx.interpreted_horizon is HorizonBucket.UNKNOWN
    assert "DECLARED_HORIZON_DATE_CONFLICT" in ctx.reason_codes and ctx.consistency_status == "NEEDS_CLARIFICATION"
    assert deterministic(svc) == before


def test_E_unexpected_interpreter_exception_is_contained():
    class Exploding:
        def interpret(self, context):
            raise RuntimeError("unexpected client failure")
    base = build_service()
    svc = BousslaAppService(base.store, base.registry, settings=base.settings,
                            context_assistant=ContextConsistencyAssistant(Exploding()))
    before = deterministic(svc)
    ctx = declare(svc, "e2", declared_horizon="SHORT_HORIZON", stage="Gros œuvre", **LONG).context_assessment
    assert ctx.interpretation_mode is Mode.TEMPLATE and "DECLARED_HORIZON_DATE_CONFLICT" in ctx.reason_codes
    assert deterministic(svc) == before


def test_F_company_corrects_horizon_via_answers_becomes_consistent():
    svc = service()
    before = deterministic(svc)
    declare(svc, "f", declared_horizon="SHORT_HORIZON", **LONG)
    first = svc.get_case(actors(svc)[0], CASE).context_assessment
    assert first.consistency_status == "NEEDS_CLARIFICATION"
    analysis = svc.start_analysis(actors(svc)[0], CASE, ver(svc))
    asked = [q.question_id for q in analysis.questions]
    assert asked[:2] == ["Q-HORIZON-CONFIRM", "Q-PROJECT-ALLOCATION"] or "Q-HORIZON-CONFIRM" in asked
    v_before_answer = ver(svc)
    svc.answer_questions(actors(svc)[0], CASE, analysis.analysis_id,
                         {"Q-HORIZON-CONFIRM": "LONGER_HORIZON", "Q-PROJECT-STAGE": "Gros œuvre"}, ver(svc), "ans")
    after = svc.get_case(actors(svc)[0], CASE).context_assessment
    assert after.consistency_status == "CONSISTENT" and after.declared_horizon is HorizonBucket.LONGER_HORIZON
    assert after.claim_id != first.claim_id
    claims = {c.claim_id: c for c in svc.store.facts(CASE, "context_claim", ContextClaim)}
    assert claims[after.claim_id].supersedes_claim_id == first.claim_id
    assert claims[first.claim_id].declared_horizon is HorizonBucket.SHORT_HORIZON  # history immutable
    old = {c.claim_id for c in svc.store.facts(CASE, "context_claim", ContextClaim, version=v_before_answer)}
    assert first.claim_id in old and after.claim_id not in old
    assert "Q-HORIZON-CONFIRM" not in company_questions(svc)  # answered: not asked again
    assert deterministic(svc) == before


def test_global_budget_is_three_and_answered_ids_are_not_repeated():
    svc = service()
    declare(svc, "g", declared_horizon="SHORT_HORIZON", beneficiary_type="UNKNOWN",
            planned_start="2027-01-01", planned_end="2028-06-30")
    qs = company_questions(svc)
    assert len(qs) == 3 and qs[0] == "Q-HORIZON-CONFIRM" and len(set(qs)) == 3


def test_malformed_declared_horizon_and_answer_are_typed_errors():
    svc = service()
    v = ver(svc)
    with pytest.raises(BousslaError) as e:
        declare(svc, "bad", declared_horizon="MEDIUM")
    assert e.value.code is ErrorCode.INSUFFICIENT_INFORMATION and ver(svc) == v
    analysis = svc.start_analysis(actors(svc)[0], CASE, v)
    with pytest.raises(BousslaError) as e:
        svc.answer_questions(actors(svc)[0], CASE, analysis.analysis_id, {"Q-HORIZON-CONFIRM": "bientôt"}, v, "x")
    assert e.value.code is ErrorCode.INSUFFICIENT_INFORMATION and ver(svc) == v


def test_declared_horizon_defaults_to_unknown_and_is_never_derived():
    svc = service()
    ctx = declare(svc, "h", stage="Gros œuvre", **LONG).context_assessment
    assert ctx.declared_horizon is HorizonBucket.UNKNOWN and ctx.calculated_horizon is HorizonBucket.LONGER_HORIZON
    latest = svc._context_base_claim("DEMO-BAT", {"context_claim": svc.store.facts(CASE, "context_claim", ContextClaim)})
    assert latest.declared_horizon is HorizonBucket.UNKNOWN


def test_model_payload_is_bounded_and_reference_expected_is_server_side():
    stub = ModelStub("CONSTRUCTION_PROJECT", "LONGER_HORIZON", "environ dix-huit mois", ["dépôt logistique"])
    svc = service(stub)
    declare(svc, "i", declared_horizon="SHORT_HORIZON", reference_expected="true", project_reference="REF-X", **LONG)
    body = json.loads(stub.requests[-1]["input"][1]["content"])
    assert set(body) == {"purpose_text", "declared_purpose_category", "declared_horizon", "planned_start",
                         "planned_end", "stage"}
    dumped = json.dumps(stub.requests, ensure_ascii=False)
    assert not [t for t in FORBIDDEN if t in dumped]
    ctx = svc.get_case(actors(svc)[0], CASE).context_assessment
    assert "LONG_HORIZON_REFERENCE_MISSING" not in ctx.reason_codes  # browser cannot set reference_expected


def test_company_and_officer_views_and_caching():
    stub = ModelStub("CONSTRUCTION_PROJECT", "LONGER_HORIZON", "environ dix-huit mois", ["dépôt logistique"])
    svc = service(stub)
    declare(svc, "j", declared_horizon="LONGER_HORIZON", stage="Gros œuvre", **LONG)
    calls = len(stub.requests)
    company = svc.get_case(actors(svc)[0], CASE)
    officer = svc.get_case(actors(svc)[1], CASE)
    for _ in range(3):
        svc.get_case(actors(svc)[0], CASE)
    assert len(stub.requests) == calls  # cached per version/claim
    assert company.context_assessment == officer.context_assessment
    assert "findings" not in type(company).model_fields and officer.mode_by_node["context"] is Mode.LIVE
    assert "risk" not in company.context_assessment.model_dump_json().lower()


def test_langgraph_analysis_carries_context_questions_and_recomputes():
    svc = service()
    declare(svc, "k", declared_horizon="SHORT_HORIZON", stage="Gros œuvre", **LONG)
    runner = WorkflowRunner(svc, planner=None)
    view = runner.run_analysis(actors(svc)[0], CASE, ver(svc))
    assert view.status is AnalysisStatus.AWAITING_COMPANY_ANSWER and view.questions[0].question_id == "Q-HORIZON-CONFIRM"
    assert view.mode_by_node["context"] is Mode.NOT_RUN
    runner.submit_answers(actors(svc)[0], CASE, {"Q-HORIZON-CONFIRM": "LONGER_HORIZON"})
    assert svc.get_case(actors(svc)[0], CASE).context_assessment.consistency_status == "CONSISTENT"


def test_published_request_carries_context_questions_and_response_supersedes_claim():
    """React/Streamlit use prepare -> publish -> submit_response, not start_analysis."""
    svc = service()
    co, off = actors(svc)
    before = deterministic(svc)
    declare(svc, "r1", declared_horizon="SHORT_HORIZON", **LONG)
    draft = svc.prepare_clarification(off, CASE, ver(svc))
    ids = [q.question_id for q in draft.questions]
    assert len(ids) <= 3 and ids[0] == "Q-HORIZON-CONFIRM"
    assert next(q for q in draft.questions if q.question_id == "Q-HORIZON-CONFIRM").choices == ("SHORT_HORIZON",
                                                                                               "LONGER_HORIZON")
    req = svc.publish_clarification(off, CASE, draft.draft_id, ver(svc), "pub")
    with pytest.raises(BousslaError) as e:  # display labels are not accepted, only enum values
        svc.submit_response(co, CASE, req.request.request_id, {"answers": {"Q-HORIZON-CONFIRM": "Horizon long"}},
                            ver(svc), "bad")
    assert e.value.code is ErrorCode.INSUFFICIENT_INFORMATION
    first = svc.get_case(co, CASE).context_assessment
    svc.submit_response(co, CASE, req.request.request_id,
                        {"answers": {"Q-HORIZON-CONFIRM": "LONGER_HORIZON"}}, ver(svc), "ok")
    after = svc.get_case(co, CASE).context_assessment
    assert after.declared_horizon is HorizonBucket.LONGER_HORIZON and after.claim_id != first.claim_id
    assert "DECLARED_HORIZON_DATE_CONFLICT" not in after.reason_codes
    claims = {c.claim_id: c for c in svc.store.facts(CASE, "context_claim", ContextClaim)}
    assert claims[first.claim_id].declared_horizon is HorizonBucket.SHORT_HORIZON  # history immutable
    assert deterministic(svc) == before


def test_brick_case_published_request_unchanged():
    svc = service()
    draft = svc.prepare_clarification(actors(svc)[1], CASE, ver(svc))
    assert [q.question_id for q in draft.questions] == ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]
