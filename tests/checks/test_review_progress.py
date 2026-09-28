"""An unresolved cause changes only when scoped evidence changes its stage."""

import pytest

from boussla.contracts import EvidenceRef, Finding, FindingFamily, FindingStatus, ProgressStage
from boussla.review_progress import ProgressEvidence, calculate_progress, transaction_progress_index


def finding(family=FindingFamily.QUANTITY, *, status=FindingStatus.UNRESOLVED,
            severity="1", transaction_id="TX-001", sourced=True):
    return Finding(
        finding_id=f"{transaction_id}:{family.value}", case_id="CASE-001", company_id="DEMO-BAT",
        transaction_id=transaction_id, family=family, status=status, severity=severity,
        evidence_refs=(EvidenceRef(document_id="BASE-DOC"),) if sourced else (),
        calculation_version="TEST", case_version=1,
    )


@pytest.mark.parametrize("evidence,stage,current,provisional", [
    (ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY),
     ProgressStage.UNRESOLVED, "40", False),
    (ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY, response_id="R1"),
     ProgressStage.EXPLANATION_RECEIVED, "30", True),
    (ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                      response_id="R1", document_id="D2"),
     ProgressStage.EVIDENCE_RECEIVED, "20", True),
    (ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                      response_id="R1", document_id="D2", technically_consistent=True),
     ProgressStage.EVIDENCE_COHERENT, "10", True),
])
def test_quantity_cause_has_business_stage_and_proportional_contribution(evidence, stage, current, provisional):
    [cause] = calculate_progress((finding(),), (evidence,))
    assert cause.raw_contribution == "40"
    assert cause.current_contribution == current
    assert cause.stage is stage
    assert cause.provisional is provisional
    assert transaction_progress_index((cause,), "TX-001") == int(current)


def test_only_accepted_and_explained_cause_reaches_zero():
    explained = finding(status=FindingStatus.EXPLAINED, severity="0")
    evidence = ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                                response_id="R1", document_id="D2", technically_consistent=True,
                                officer_accepted=True, prior_raw_contribution="40")
    [cause] = calculate_progress((explained,), (evidence,))
    assert (cause.raw_contribution, cause.current_contribution) == ("40", "0")
    assert cause.stage is ProgressStage.RESOLVED
    assert cause.provisional is False


def test_new_contradiction_revokes_earlier_coherence_and_raises_index():
    coherent = ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                                response_id="R1", document_id="D2", technically_consistent=True)
    contradicted = coherent.model_copy(update={"contradiction_reason": "QUANTITY_MISMATCH"})
    [before] = calculate_progress((finding(),), (coherent,))
    [after] = calculate_progress((finding(),), (contradicted,))
    assert transaction_progress_index((before,), "TX-001") == 10
    assert transaction_progress_index((after,), "TX-001") == 40
    assert after.stage is ProgressStage.UNRESOLVED
    assert after.reason_code == "QUANTITY_MISMATCH"


def test_rejection_revokes_provisional_reduction():
    rejected = ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                                response_id="R1", document_id="D2", rejected=True)
    [cause] = calculate_progress((finding(),), (rejected,))
    assert cause.current_contribution == "40"
    assert cause.stage is ProgressStage.UNRESOLVED


def test_distinct_families_use_their_own_weights_and_duplicate_findings_count_once():
    findings = (finding(FindingFamily.COUNTERPARTY, severity="0.5"),
                finding(FindingFamily.COUNTERPARTY, severity="0.4"),
                finding(FindingFamily.SETTLEMENT, severity="1"))
    evidence = (ProgressEvidence(transaction_id="TX-001", family=FindingFamily.COUNTERPARTY,
                                 response_id="R1"),)
    causes = calculate_progress(findings, evidence)
    assert [(c.family, c.raw_contribution, c.current_contribution) for c in causes] == [
        (FindingFamily.COUNTERPARTY, "17.5", "13.125"),
        (FindingFamily.SETTLEMENT, "25", "25"),
    ]
    assert transaction_progress_index(causes, "TX-001") == 38


def test_missing_evidence_never_creates_adverse_cause_and_tiny_unresolved_stays_positive():
    insufficient = finding(FindingFamily.COUNTERPARTY, status=FindingStatus.INSUFFICIENT,
                           severity=None, sourced=False)
    tiny = finding(severity="0.01")
    [cause] = calculate_progress((insufficient, tiny), (
        ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                         response_id="R1", document_id="D2", technically_consistent=True),
    ))
    assert cause.current_contribution == "0.1"
    assert transaction_progress_index((cause,), "TX-001") == 1


def test_accepted_but_unresolved_cause_keeps_full_residual_contribution():
    source = ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                              response_id="R1", document_id="D1", officer_accepted=True,
                              technically_consistent=True, prior_raw_contribution="40")
    [cause] = calculate_progress((finding(severity="0.5"),), (source,))
    assert cause.current_contribution == "20"
    assert cause.stage is ProgressStage.UNRESOLVED
    assert cause.reason_code == "ACCEPTED_EVIDENCE_RESIDUAL"


def test_loss_of_support_can_restore_each_earlier_stage():
    coherent = ProgressEvidence(transaction_id="TX-001", family=FindingFamily.QUANTITY,
                                response_id="R1", document_id="D1", technically_consistent=True)
    variants = (coherent, coherent.model_copy(update={"technically_consistent": False}),
                coherent.model_copy(update={"document_id": None}),
                coherent.model_copy(update={"response_id": None}))
    assert [transaction_progress_index(calculate_progress((finding(),), (v,)), "TX-001")
            for v in variants] == [10, 20, 30, 40]


def test_same_reason_code_does_not_link_an_answer_to_another_transaction():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from boussla.contracts import ClarificationRequest, ClarificationResponse, RequestStatus
    from boussla.review_evidence import derive_progress_evidence
    a = finding(FindingFamily.COUNTERPARTY).model_copy(update={"reason_code": "GAP"})
    b = finding(FindingFamily.COUNTERPARTY, transaction_id="TX-002").model_copy(update={
        "reason_code": "GAP", "evidence_refs": (EvidenceRef(document_id="OTHER-DOC"),)})
    request = ClarificationRequest(request_id="REQ", case_id="CASE-001", company_id="DEMO-BAT",
                                   case_version=1, status=RequestStatus.RESPONDED,
                                   fact_ids=("BASE-DOC",), reason_codes=("GAP",))
    response = ClarificationResponse(response_id="R1", request_id="REQ", author_actor_id="COMPANY",
                                     submitted_at=datetime.now(timezone.utc),
                                     answers={"Q-COUNTERPART-RECORD": "Voici la référence"})
    evidence = derive_progress_evidence((a, b), {"request": [SimpleNamespace(request=request)],
                                               "response": [response]}, None)
    assert [e.transaction_id for e in evidence] == ["TX-001"]
