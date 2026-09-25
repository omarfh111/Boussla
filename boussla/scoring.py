"""Versioned review-priority baseline and independent evidence coverage."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from boussla.contracts import Finding, FindingFamily, FindingStatus, ScoreResult

METHOD = "CONTEXT_RULES_V4_1"
WEIGHTS = {
    FindingFamily.COUNTERPARTY: Decimal(35),
    FindingFamily.SETTLEMENT: Decimal(25),
    FindingFamily.QUANTITY: Decimal(40),
}


def _supported(findings: list[Finding]) -> list[Finding]:
    supported = []
    for finding in findings:
        if not finding.evidence_refs:
            continue
        if finding.status is FindingStatus.EXPLAINED:
            supported.append(finding)
        elif finding.status is FindingStatus.UNRESOLVED and finding.severity is not None:
            severity = Decimal(finding.severity)
            if Decimal(0) <= severity <= Decimal(1):
                supported.append(finding)
    return supported


def score_transaction(findings: list[Finding], applicability: set[FindingFamily]) -> ScoreResult:
    """Score supported unresolved families once; never renormalize unknowns."""
    transaction_ids = {finding.transaction_id for finding in findings}
    if len(transaction_ids) != 1:
        raise ValueError("findings must refer to exactly one transaction")
    if not applicability <= WEIGHTS.keys():
        raise ValueError("unknown finding family")
    contributions: dict[str, str] = {}
    evaluable: list[FindingFamily] = []
    unknown: list[FindingFamily] = []
    total = Decimal(0)
    for family in sorted(applicability, key=lambda item: item.value):
        family_findings = _supported([f for f in findings if f.family is family])
        if not family_findings:
            unknown.append(family)
            continue
        evaluable.append(family)
        severity = max((Decimal(f.severity) for f in family_findings
                        if f.status is FindingStatus.UNRESOLVED), default=Decimal(0))
        contribution = WEIGHTS[family] * severity
        contributions[family.value] = str(contribution)
        total += contribution
    known_not_applicable = {f.family for f in findings if f.status is FindingStatus.NOT_APPLICABLE}
    coverage_complete = (not unknown and all(
        family in applicability or family in known_not_applicable for family in WEIGHTS
    ))
    coverage = (str(Decimal(100) * Decimal(len(evaluable)) / Decimal(len(applicability)))
                if applicability else None)
    return ScoreResult(
        transaction_id=next(iter(transaction_ids)),
        review_index=int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP)) if evaluable else None,
        evidence_coverage=coverage,
        coverage_complete=coverage_complete,
        evaluable_families=tuple(evaluable), unknown_families=tuple(unknown),
        contributions=contributions, method=METHOD,
    )


def aggregate_company(transaction_scores: list[ScoreResult]) -> int | None:
    """Maximum evaluable transaction index in the supplied scope."""
    indices = [score.review_index for score in transaction_scores if score.review_index is not None]
    return max(indices) if indices else None


def count_unresolved_transactions(findings: Iterable[Finding]) -> int:
    """Count economic events, not documents, reruns or finding rows."""
    return len({finding.transaction_id for finding in findings
                if finding.status is FindingStatus.UNRESOLVED and finding.evidence_refs})
