"""Fixed V4 index, coverage and economic-event aggregation."""

from boussla.contracts import EvidenceRef, Finding, FindingFamily, FindingStatus
from boussla.scoring import aggregate_company, count_unresolved_transactions, score_transaction


def _finding(family, status, *, severity=None, transaction_id="TX-001", sourced=True):
    return Finding(
        finding_id=f"{transaction_id}:{family.value}:{status.value}",
        case_id="CASE-001", company_id="DEMO-BAT", transaction_id=transaction_id,
        family=family, status=status, severity=severity,
        evidence_refs=(EvidenceRef(document_id="DOC-001"),) if sourced else (),
        calculation_version="TEST", case_version=1,
    )


def test_main_case_scores_40_with_full_coverage():
    findings = [
        _finding(FindingFamily.COUNTERPARTY, FindingStatus.EXPLAINED, severity="0"),
        _finding(FindingFamily.SETTLEMENT, FindingStatus.EXPLAINED, severity="0"),
        _finding(FindingFamily.QUANTITY, FindingStatus.UNRESOLVED, severity="1"),
    ]
    score = score_transaction(findings, set(FindingFamily))
    assert score.review_index == 40
    assert score.evidence_coverage == "100"
    assert score.coverage_complete
    assert score.contributions == {"COUNTERPARTY": "0", "QUANTITY": "40", "SETTLEMENT": "0"}


def test_unknown_family_does_not_erase_supported_gap_or_renormalize():
    findings = [
        _finding(FindingFamily.COUNTERPARTY, FindingStatus.INSUFFICIENT, sourced=False),
        _finding(FindingFamily.SETTLEMENT, FindingStatus.INSUFFICIENT, sourced=False),
        _finding(FindingFamily.QUANTITY, FindingStatus.UNRESOLVED, severity="1"),
    ]
    score = score_transaction(findings, set(FindingFamily))
    assert score.review_index == 40
    assert score.evidence_coverage.startswith("33.333")
    assert not score.coverage_complete
    assert set(score.unknown_families) == {FindingFamily.COUNTERPARTY, FindingFamily.SETTLEMENT}


def test_no_evaluable_check_has_null_index():
    findings = [_finding(FindingFamily.QUANTITY, FindingStatus.INSUFFICIENT, sourced=False)]
    score = score_transaction(findings, {FindingFamily.QUANTITY})
    assert score.review_index is None
    assert score.evidence_coverage == "0"
    assert not score.coverage_complete


def test_duplicate_issue_counts_once_and_rounds_half_up():
    findings = [
        _finding(FindingFamily.COUNTERPARTY, FindingStatus.UNRESOLVED, severity="0.4"),
        _finding(FindingFamily.COUNTERPARTY, FindingStatus.UNRESOLVED, severity="0.5"),
    ]
    score = score_transaction(findings, {FindingFamily.COUNTERPARTY})
    assert score.review_index == 18
    assert score.contributions["COUNTERPARTY"] == "17.5"


def test_unsourced_unresolved_finding_cannot_contribute():
    finding = _finding(FindingFamily.QUANTITY, FindingStatus.UNRESOLVED,
                       severity="1", sourced=False)
    assert score_transaction([finding], {FindingFamily.QUANTITY}).review_index is None


def test_company_policy_is_max_and_unresolved_count_is_distinct():
    severe = _finding(FindingFamily.QUANTITY, FindingStatus.UNRESOLVED, severity="1")
    lesser = _finding(FindingFamily.QUANTITY, FindingStatus.UNRESOLVED,
                      severity="0.5", transaction_id="TX-002")
    score1 = score_transaction([severe], {FindingFamily.QUANTITY})
    score2 = score_transaction([lesser], {FindingFamily.QUANTITY})
    assert aggregate_company([score1, score2]) == 40
    assert aggregate_company([]) is None
    assert count_unresolved_transactions([severe, severe, lesser]) == 2
