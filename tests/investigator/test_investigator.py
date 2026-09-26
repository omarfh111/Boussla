import json
from dataclasses import asdict

import httpx
import pytest

from boussla.contracts import Audience, ClarificationStatus, FindingFamily, FindingStatus, Mode
from boussla.investigator import (
    ClarificationDigest, ContextDigest, EvidenceFeature, FindingDigest, HYPOTHESIS_CATALOGUE,
    HypothesisSupport, InvestigatorAssistant, InvestigatorInput, ObservationKind, ScenarioDigest,
)
from boussla.investigator.selector import OpenAIInvestigatorSelector
from boussla.playbook import QUESTIONS


def case_input():
    return InvestigatorInput(
        findings=(FindingDigest(FindingFamily.QUANTITY, "ALLOCATION_EXCEEDS_INVOICED_QUANTITY",
                                FindingStatus.UNRESOLVED, ("EV_BUYER", "EV_SELLER"),
                                ("ALLOCATION_REFERENCE",)),),
        evidence_features=(EvidenceFeature("SECOND_PROJECT_ALLOCATION", ("EV_BUYER",),
                                           ("EV_SELLER",), ("PROJECT_REFERENCE",)),),
        context=ContextDigest("CONSTRUCTION_PROJECT", "SHORT_HORIZON", "LONGER_HORIZON",
                              "NEEDS_CLARIFICATION", ("DECLARED_HORIZON_DATE_CONFLICT",)),
        history_signal_codes=("REVISION_ADDED",),
        transaction_summary_codes=("QUANTITY_MISMATCH",),
        clarification=ClarificationDigest(ClarificationStatus.ANSWERED, ("Q-STOCK",),
                                          ("STOCK_CLAIMED",)),
        reference_rule_ids=("TN-MOF-FAQ-952-INVOICE-NUMBER",),
        scenarios=(ScenarioDigest("P2_ALLOCATION", "QUANTITY_RESOLVED", 0),),
    )


def selector_response(hypotheses, questions):
    content = json.dumps({"hypothesis_ids": hypotheses, "question_ids": questions})
    return {"status": "completed", "output": [{"content": [{"type": "output_text", "text": content}]}]}


def selector(handler):
    return OpenAIInvestigatorSelector(api_key="test-key", model="configured-model",
                                      client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_template_brief_separates_sources_and_preserves_inputs():
    data = case_input()
    before = asdict(data)
    result = InvestigatorAssistant().assess(data)
    assert asdict(data) == before
    assert result.mode is Mode.TEMPLATE and result.brief is not None
    brief = result.brief
    assert brief.mode is Mode.TEMPLATE
    assert {o.kind for o in brief.key_observations} >= {
        ObservationKind.FACT, ObservationKind.DECLARATION,
        ObservationKind.MODEL_INTERPRETATION, ObservationKind.HYPOTHETICAL_SCENARIO,
        ObservationKind.HYPOTHESIS,
    }
    assert brief.what_changed_since_previous_revision == ("REVISION_ADDED",)
    assert brief.reference_rule_ids == data.reference_rule_ids
    assert any("indice hypothétique calculé : 0" in o.text_fr for o in brief.key_observations)
    assert "ALLOCATION_REFERENCE" in brief.missing_information
    assert any("Éléments contradictoires codés" in o.text_fr for o in brief.key_observations)
    assert any("Résumé transactionnel codé : QUANTITY_MISMATCH" in o.text_fr
               for o in brief.key_observations)
    assert any("réponses codées STOCK_CLAIMED" in o.text_fr for o in brief.key_observations)
    assert len(brief.top_hypotheses) <= 5
    assert all(h.hypothesis_id in HYPOTHESIS_CATALOGUE for h in brief.top_hypotheses)


def test_mixed_support_and_contradiction_stays_candidate():
    brief = InvestigatorAssistant().assess(case_input()).brief
    assert brief is not None
    h = next(h for h in brief.top_hypotheses if h.hypothesis_id == "SECOND_PROJECT_ALLOCATION")
    assert h.status is HypothesisSupport.PLAUSIBLE
    assert h.supporting_refs == ("EV_BUYER",) and h.contradicting_refs == ("EV_SELLER",)
    assert "fraud_probability" not in asdict(brief)


def test_company_cannot_receive_officer_brief_or_invoke_model():
    def forbidden(request):
        raise AssertionError("company invoked provider")
    result = InvestigatorAssistant(selector(forbidden)).assess(case_input(), audience=Audience.COMPANY)
    assert result.brief is None and result.mode is Mode.NOT_RUN


@pytest.mark.parametrize("hypotheses,questions", [
    (["FRAUD"], []),
    (["STOCK_REMAINING"] * 6, []),
    (["STOCK_REMAINING", "STOCK_REMAINING"], []),
    (["STOCK_REMAINING"], ["Q-NOT-IN-PLAYBOOK"]),
    (["STOCK_REMAINING"], ["Q-STOCK"]),  # already answered
    (["STOCK_REMAINING"], ["Q-PURPOSE"]),  # playbook ID, but not eligible here
    (["PAYMENT_SCHEDULE"], []),  # catalogue ID, but unrelated to quantity finding
    (["STOCK_REMAINING"], ["Q-HORIZON-CONFIRM"] * 4),
])
def test_invalid_model_selection_degrades_to_template(hypotheses, questions):
    model = selector(lambda request: httpx.Response(200, json=selector_response(hypotheses, questions)))
    result = InvestigatorAssistant(model).assess(case_input())
    assert result.mode is Mode.TEMPLATE
    assert result.brief is not None and len(result.brief.top_hypotheses) <= 5
    assert all(q in QUESTIONS for q in result.brief.suggested_question_ids)
    assert "Q-STOCK" not in result.brief.suggested_question_ids


def test_valid_model_selection_is_ids_only_and_max_three_questions():
    model = selector(lambda request: httpx.Response(200, json=selector_response(
        ["SECOND_PROJECT_ALLOCATION", "STOCK_REMAINING"],
        ["Q-HORIZON-CONFIRM", "Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC"],
    )))
    result = InvestigatorAssistant(model).assess(case_input())
    assert result.mode is Mode.LIVE
    assert [h.hypothesis_id for h in result.brief.top_hypotheses] == [
        "SECOND_PROJECT_ALLOCATION", "STOCK_REMAINING"]
    assert result.brief.suggested_question_ids == (
        "Q-HORIZON-CONFIRM", "Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC")


def test_payload_excludes_identity_finances_evidence_refs_and_scenario_index():
    def handler(request):
        payload = json.loads(request.content)
        assert payload["store"] is False and payload["model"] == "configured-model"
        supplied = json.loads(payload["input"][1]["content"])
        assert set(supplied) == {
            "findings", "evidence_features", "context", "history_signal_codes",
            "transaction_summary_codes", "clarification", "reference_rule_ids",
            "scenario_outcome_codes", "hypothesis_allowlist", "question_allowlist",
        }
        raw = request.content.decode()
        for forbidden in ("EV_BUYER", "EV_SELLER", "hypothetical_review_index",
                          "review_index", "company_id", "tax_id", "payment_id", "invoice_amount"):
            assert forbidden not in raw
        assert supplied["history_signal_codes"] == ["REVISION_ADDED"]
        assert supplied["clarification"]["answer_codes"] == ["STOCK_CLAIMED"]
        return httpx.Response(200, json=selector_response(["SECOND_PROJECT_ALLOCATION"], []))
    assert InvestigatorAssistant(selector(handler)).assess(case_input()).mode is Mode.LIVE


def test_provider_outage_is_nonfatal_and_does_not_change_case_input():
    data = case_input()
    before = asdict(data)
    model = selector(lambda request: httpx.Response(503))
    result = InvestigatorAssistant(model).assess(data)
    assert result.mode is Mode.TEMPLATE and result.brief is not None
    assert asdict(data) == before


def test_free_text_and_unscoped_evidence_are_rejected_before_provider():
    with pytest.raises(ValueError):
        InvestigatorInput(history_signal_codes=("PRIVATE-COMPANY 123456",))
    with pytest.raises(ValueError):
        InvestigatorInput(history_signal_codes=("COMPANY_123456789",))
    with pytest.raises(ValueError):
        InvestigatorInput(findings=case_input().findings,
                          evidence_features=(EvidenceFeature("STOCK_REMAINING", ("OTHER_CASE",)),))


def test_no_finding_has_no_invented_hypothesis_or_score():
    result = InvestigatorAssistant().assess(InvestigatorInput())
    assert result.brief.top_hypotheses == ()
    assert result.brief.suggested_question_ids == ()
    assert result.brief.reference_rule_ids == ()


def test_bounded_many_findings_do_not_hide_scenario_or_reference_caveat():
    base = case_input()
    data = InvestigatorInput(findings=base.findings * 12, evidence_features=base.evidence_features,
                             reference_rule_ids=base.reference_rule_ids, scenarios=base.scenarios)
    brief = InvestigatorAssistant().assess(data).brief
    assert any(o.kind is ObservationKind.HYPOTHETICAL_SCENARIO for o in brief.key_observations)
    assert any("Passages publics candidats" in o.text_fr for o in brief.key_observations)
