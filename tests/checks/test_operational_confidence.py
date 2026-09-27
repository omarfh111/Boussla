"""The approved trust contract is a normalized, source-backed indicator."""

from datetime import datetime, timedelta, timezone

from boussla.contracts import (ClarificationRequest, ClarificationResponse, EvidenceProposal,
                               FindingFamily, Mode, ProposalStatus, RequestStatus, RequestView)
from boussla.operational_confidence import calculate_operational_confidence
from boussla.review_progress import ProgressEvidence


NOW = datetime(2026, 9, 27, tzinfo=timezone.utc)


def request(suffix: str, *, due_days: int = 1) -> RequestView:
    return RequestView(request=ClarificationRequest(
        request_id=f"REQ-{suffix}", case_id="CASE-1", company_id="COMP-1", case_version=1,
        status=RequestStatus.PUBLISHED_IN_DEMO, target_response_at=NOW + timedelta(days=due_days)),
        questions=(), text_fr="Justifier", mode=Mode.LIVE)


def response(suffix: str, *, days: int = 0) -> ClarificationResponse:
    return ClarificationResponse(response_id=f"RESP-{suffix}", request_id=f"REQ-{suffix}",
                                 author_actor_id="ACTOR-COMP-1", submitted_at=NOW + timedelta(days=days))


def proposal(suffix: str, status: ProposalStatus) -> EvidenceProposal:
    return EvidenceProposal(proposal_id=f"PROP-{suffix}", case_id="CASE-1", expected_version=1,
                            source_response_id=f"RESP-{suffix}", source_document_id=f"DOC-{suffix}",
                            transaction_id=f"TX-{suffix}", line_id="L-1", unit="unit",
                            budget_quantity="1", changes=(), status=status)


def evidence(suffix: str, *, consistent: bool) -> ProgressEvidence:
    return ProgressEvidence(transaction_id=f"TX-{suffix}", family=FindingFamily.QUANTITY,
                            response_id=f"RESP-{suffix}", document_id=f"DOC-{suffix}",
                            proposal_id=f"PROP-{suffix}", technically_consistent=consistent,
                            contradiction_reason=None if consistent else "DOCUMENT_ALLOCATION_CONTRADICTION")


def calculate(requests=(), responses=(), proposals=(), evidence_items=(), covered=(), conflicted=(), cutoff=NOW):
    return calculate_operational_confidence(requests, responses, proposals, (), cutoff,
                                            evidence_items, covered, conflicted)


def test_pending_before_target_and_two_eligible_events_are_unknown():
    pending = calculate((request("1"), request("2")))
    assert pending.index is None and pending.status == "INSUFFICIENT_DATA"
    assert pending.eligible_observations == 0
    two = calculate((request("1"), request("2")), (response("1"), response("2")))
    assert two.index is None and two.eligible_observations == 2


def test_four_dimensions_have_explicit_denominators_and_weighted_contributions():
    result = calculate(
        (request("1"), request("2"), request("3")),
        (response("1"), response("2"), response("3", days=2)),
        (proposal("1", ProposalStatus.ACCEPTED), proposal("2", ProposalStatus.REJECTED)),
        (evidence("1", consistent=True), evidence("2", consistent=False)),
        ("TX-1", "TX-2", "TX-3", "TX-4"), ("TX-4",), NOW + timedelta(days=2),
    )
    assert result.status == "AVAILABLE" and result.index == 60
    assert result.as_of == NOW + timedelta(days=2) and result.eligible_observations == 9
    factors = {f.code: f for f in result.factors}
    assert {code: (f.numerator, f.denominator, f.nominal_weight)
            for code, f in factors.items()} == {
        "TIMELINESS": (2, 3, 30), "ANSWER_COHERENCE": (1, 2, 25),
        "EVIDENCE_CORROBORATION": (1, 2, 25), "HISTORICAL_STABILITY": (3, 4, 20)}
    assert all(f.source_ids and f.reason_codes for f in factors.values())
    assert {f.weighted_contribution for f in factors.values()} == {"20", "12.5", "15"}


def test_missing_dimensions_are_omitted_and_weights_renormalized():
    result = calculate((request("1"), request("2"), request("3")),
                       (response("1"), response("2"), response("3", days=2)), cutoff=NOW + timedelta(days=2))
    assert result.index == 67
    assert len(result.factors) == 1
    assert result.factors[0].code == "TIMELINESS"
    assert result.factors[0].effective_weight == "100"


def test_rejected_then_accepted_proof_recalculates_without_moving_documentary_score():
    requests = (request("1"), request("2"))
    responses = (response("1"), response("2"))
    rejected = calculate(requests, responses, (proposal("1", ProposalStatus.REJECTED),))
    accepted = calculate(requests, responses, (proposal("1", ProposalStatus.ACCEPTED),))
    assert rejected.index == 55 and accepted.index == 100
    assert rejected.eligible_observations == accepted.eligible_observations == 3
    assert "PROP-1" in next(f.source_ids for f in rejected.factors
                            if f.code == "EVIDENCE_CORROBORATION")


def test_new_contradictory_proof_reverses_answer_coherence():
    requests = (request("1"), request("2"), request("3"))
    responses = (response("1"), response("2"), response("3"))
    good = calculate(requests, responses, evidence_items=(evidence("1", consistent=True),))
    bad = calculate(requests, responses, evidence_items=(evidence("1", consistent=False),))
    assert good.index == 100 and bad.index == 55
    assert "DOCUMENT_ALLOCATION_CONTRADICTION" in next(f.reason_codes for f in bad.factors
                                                         if f.code == "ANSWER_COHERENCE")


def test_covered_history_uses_distinct_transactions_not_missing_months():
    stable = calculate(covered=("TX-1", "TX-2", "TX-3"))
    conflict = calculate(covered=("TX-1", "TX-2", "TX-3"), conflicted=("TX-2",))
    assert stable.index == 100 and conflict.index == 67
    assert conflict.factors[0].denominator == 3 and conflict.factors[0].numerator == 2


def test_one_response_cannot_count_twice_toward_minimum_sample():
    result = calculate((request("1"), request("2")), (response("1"), response("2")),
                       evidence_items=(evidence("1", consistent=True),))
    assert result.index is None and result.sample_size == 2
    assert result.data_quality == "INSUFFICIENT_DATA"


def test_small_numeric_sample_is_explicitly_limited_and_windowed():
    result = calculate((request("1", due_days=-1), request("2", due_days=-1), request("3", due_days=-1)))
    assert result.index == 0 and result.data_quality == "LIMITED_DATA"
    assert result.request_count == 3 and result.document_count == 0
    assert "3 éléments distincts" in result.sample_note_fr
    assert result.window_start.year == NOW.year - 1
    assert calculate((request("ancient", due_days=-400),)).sample_size == 0
