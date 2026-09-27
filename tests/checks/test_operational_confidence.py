"""Operational trust reflects attributed interactions, never documentary risk."""

from datetime import datetime, timedelta, timezone

from boussla.contracts import (ClarificationRequest, ClarificationResponse, EvidenceProposal,
                               ProposalStatus, RequestStatus, RequestView, HistorySignalCode,
                               CompanyHistorySignal, Mode, CauseProgress, FindingFamily, ProgressStage)
from boussla.operational_confidence import calculate_operational_confidence


NOW = datetime(2026, 9, 27, tzinfo=timezone.utc)


def request(suffix: str, *, due_days: int = 1) -> RequestView:
    return RequestView(request=ClarificationRequest(
        request_id=f"REQ-{suffix}", case_id="CASE-1", company_id="COMP-1", case_version=1,
        status=RequestStatus.PUBLISHED_IN_DEMO, target_response_at=NOW + timedelta(days=due_days)),
        questions=(), text_fr="Justifier", mode=Mode.LIVE)


def response(suffix: str, *, days: int = 0) -> ClarificationResponse:
    return ClarificationResponse(response_id=f"RESP-{suffix}", request_id=f"REQ-{suffix}",
                                 author_actor_id="ACTOR-COMP-1", submitted_at=NOW + timedelta(days=days))


def proposal(status: ProposalStatus) -> EvidenceProposal:
    return EvidenceProposal(proposal_id="PROP-1", case_id="CASE-1", expected_version=1,
                            source_response_id="RESP-1", transaction_id="TX-1", line_id="L-1",
                            unit="unit", budget_quantity="1", changes=(), status=status)


def signal(code=HistorySignalCode.REPEATED_INVOICE_CONFLICT) -> CompanyHistorySignal:
    return CompanyHistorySignal(signal_id="SIG-1", company_id="COMP-1",
                                reason_code=code,
                                period="2026-08", metric="count", observed_value="3",
                                explanation_fr="Conflits répétés", method="SYNTHETIC_SELF_HISTORY_V2", mode=Mode.LIVE)


def test_insufficient_observations_do_not_create_numeric_trust():
    assert calculate_operational_confidence((), (), (), (), NOW).index is None
    assert calculate_operational_confidence((request("1"),), (), (), (), NOW).status == "INSUFFICIENT_DATA"


def test_response_and_accepted_proof_improve_trust_and_rejection_reverses_it():
    requests = (request("1"),)
    responses = (response("1"),)
    pending = calculate_operational_confidence(requests, responses, (proposal(ProposalStatus.AWAITING_HUMAN_REVIEW),), (), NOW)
    accepted = calculate_operational_confidence(requests, responses, (proposal(ProposalStatus.ACCEPTED),), (), NOW)
    rejected = calculate_operational_confidence(requests, responses, (proposal(ProposalStatus.REJECTED),), (), NOW)
    assert pending.status == accepted.status == rejected.status == "AVAILABLE"
    assert accepted.index > pending.index > rejected.index
    assert sum(f.contribution for f in accepted.factors) + accepted.baseline == accepted.index
    assert any("PROP-1" in f.source_ids for f in rejected.factors)


def test_late_response_unanswered_request_and_repeated_anomaly_are_attributed():
    timely = calculate_operational_confidence((request("1"), request("2", due_days=-1)),
                                               (response("1"),), (), (), NOW)
    late = calculate_operational_confidence((request("1"), request("2", due_days=-1)),
                                             (response("1", days=2),), (), (signal(),), NOW + timedelta(days=2))
    assert late.index < timely.index
    assert {f.code for f in late.factors} >= {"LATE_RESPONSE", "UNANSWERED_REQUEST", "REPEATED_ANOMALY"}
    assert all(f.source_ids for f in late.factors)


def test_coherent_then_contradictory_proof_reverses_trust_independent_of_review():
    interactions = ((request("1"),), (response("1"),), (proposal(ProposalStatus.AWAITING_HUMAN_REVIEW),))
    coherent = CauseProgress(transaction_id="TX-1", family=FindingFamily.QUANTITY,
                             raw_contribution="40", current_contribution="10",
                             stage=ProgressStage.EVIDENCE_COHERENT, provisional=True,
                             source_ids=("DOC-1",))
    contradicted = coherent.model_copy(update={"stage": ProgressStage.UNRESOLVED,
                                                 "reason_code": "DOCUMENT_ALLOCATION_CONTRADICTION",
                                                 "source_ids": ("DOC-2",)})
    good = calculate_operational_confidence(*interactions, (), NOW, (coherent,))
    bad = calculate_operational_confidence(*interactions, (), NOW, (contradicted,))
    assert good.index > bad.index
    assert {f.code for f in good.factors} >= {"DOCUMENT_COHERENT"}
    assert {f.code for f in bad.factors} >= {"DOCUMENT_CONTRADICTORY"}
    assert "DOC-2" in next(f.source_ids for f in bad.factors if f.code == "DOCUMENT_CONTRADICTORY")


def test_covered_stable_history_is_positive_but_missing_history_is_not():
    interactions = ((request("1"),), (response("1"),), (proposal(ProposalStatus.ACCEPTED),))
    without = calculate_operational_confidence(*interactions, (), NOW)
    stable = calculate_operational_confidence(*interactions,
                                              (signal(HistorySignalCode.NO_SIGNIFICANT_CHANGE),), NOW)
    assert stable.index > without.index
    assert "HISTORY_STABILITY" in {f.code for f in stable.factors}


def test_answer_after_missed_target_improves_confidence_but_remains_late():
    requests = (request("1", due_days=-1), request("2", due_days=-1))
    before = calculate_operational_confidence(requests, (), (), (), NOW)
    after = calculate_operational_confidence(requests, (response("1"),), (), (), NOW)
    assert after.index > before.index
    assert {f.code for f in after.factors} >= {"LATE_RESPONSE", "UNANSWERED_REQUEST"}
