"""Trust changes are reconstructible at declared cutoffs with factor deltas."""

from datetime import datetime, timedelta, timezone

from boussla.confidence_history import confidence_delta
from boussla.contracts import ClarificationRequest, Mode, RequestStatus, RequestView
from boussla.contracts import ClarificationResponse, EvidenceProposal, ProposalStatus
from boussla.operational_confidence import calculate_operational_confidence


NOW = datetime(2026, 9, 27, tzinfo=timezone.utc)


def test_deadline_only_change_exposes_before_after_factor_and_sources():
    requests = tuple(RequestView(request=ClarificationRequest(
        request_id=f"REQ-{i}", case_id="CASE-1", company_id="COMP-1", case_version=1,
        status=RequestStatus.PUBLISHED_IN_DEMO, target_response_at=NOW + timedelta(days=1)),
        questions=(), text_fr="Justifier", mode=Mode.LIVE) for i in range(3))
    before = calculate_operational_confidence(requests, (), (), (), NOW)
    after = calculate_operational_confidence(requests, (), (), (), NOW + timedelta(days=2))
    change = confidence_delta(before, after, from_version=1, to_version=1)
    assert change is not None
    assert change.before_index is None and change.after_index == 0
    assert change.as_of == NOW + timedelta(days=2)
    [factor] = change.factor_deltas
    assert factor.code == "TIMELINESS"
    assert factor.before_contribution is None and factor.after_contribution == "0"
    assert set(factor.source_ids) == {"REQ-0", "REQ-1", "REQ-2"}


def test_rejection_then_acceptance_has_reversible_factor_delta():
    requests = tuple(RequestView(request=ClarificationRequest(
        request_id=f"REQ-{i}", case_id="CASE-1", company_id="COMP-1", case_version=1,
        status=RequestStatus.RESPONDED, target_response_at=NOW + timedelta(days=1)),
        questions=(), text_fr="Justifier", mode=Mode.LIVE) for i in range(2))
    responses = tuple(ClarificationResponse(response_id=f"RESP-{i}", request_id=f"REQ-{i}",
                                            author_actor_id="COMP-ACTOR", submitted_at=NOW) for i in range(2))
    proof = EvidenceProposal(proposal_id="PROP-1", case_id="CASE-1", expected_version=2,
                             source_response_id="RESP-0", source_document_id="DOC-1",
                             transaction_id="TX-1", line_id="L-1", unit="unit",
                             budget_quantity="1", changes=(), status=ProposalStatus.REJECTED)
    before = calculate_operational_confidence(requests, responses, (proof,), (), NOW)
    after = calculate_operational_confidence(requests, responses,
                                             (proof.model_copy(update={"status": ProposalStatus.ACCEPTED}),),
                                             (), NOW + timedelta(minutes=1))
    change = confidence_delta(before, after, from_version=2, to_version=3)
    assert change is not None and change.before_index == 55 and change.after_index == 100
    factor = next(f for f in change.factor_deltas if f.code == "EVIDENCE_CORROBORATION")
    assert factor.before_contribution == "0" and factor.after_contribution == "45.45"
    assert set(factor.reason_codes) == {"ACCEPTED_PROOF", "REJECTED_PROOF"}
    assert "DOC-1" in factor.source_ids
