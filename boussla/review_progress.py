"""Pure cause-stage calculation for the officer's documentary review index."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from boussla.contracts import (
    Contract, CauseProgress, DecimalStr, Finding, FindingFamily, FindingStatus, ProgressStage,
)
from boussla.scoring import WEIGHTS

FACTORS = {
    ProgressStage.UNRESOLVED: Decimal("1"),
    ProgressStage.EXPLANATION_RECEIVED: Decimal("0.75"),
    ProgressStage.EVIDENCE_RECEIVED: Decimal("0.50"),
    ProgressStage.EVIDENCE_COHERENT: Decimal("0.25"),
    ProgressStage.RESOLVED: Decimal("0"),
}


class ProgressEvidence(Contract):
    transaction_id: str
    family: FindingFamily
    response_id: str | None = None
    document_id: str | None = None
    proposal_id: str | None = None
    technically_consistent: bool = False
    officer_accepted: bool = False
    rejected: bool = False
    contradiction_reason: str | None = None
    prior_raw_contribution: DecimalStr | None = None


def calculate_progress(findings: tuple[Finding, ...],
                       evidence: tuple[ProgressEvidence, ...]) -> tuple[CauseProgress, ...]:
    by_key: dict[tuple[str, FindingFamily], ProgressEvidence] = {}
    for item in evidence:
        key = (item.transaction_id, item.family)
        if key in by_key:
            raise ValueError(f"duplicate progress evidence for {key}")
        by_key[key] = item

    grouped: dict[tuple[str, FindingFamily], list[Finding]] = {}
    for finding in findings:
        grouped.setdefault((finding.transaction_id, finding.family), []).append(finding)

    causes: list[CauseProgress] = []
    for (transaction_id, family), family_findings in sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1].value)):
        source = by_key.get((transaction_id, family))
        unresolved = [f for f in family_findings if f.status is FindingStatus.UNRESOLVED
                      and f.evidence_refs and f.severity is not None
                      and Decimal(0) <= Decimal(f.severity) <= Decimal(1)]
        explained = any(f.status is FindingStatus.EXPLAINED for f in family_findings)
        if unresolved:
            selected = max(unresolved, key=lambda f: Decimal(f.severity))
            raw = WEIGHTS[family] * Decimal(selected.severity)
            if source is None or source.rejected or source.contradiction_reason:
                stage = ProgressStage.UNRESOLVED
            elif source.response_id is None:
                stage = ProgressStage.UNRESOLVED
            elif source.document_id is None:
                stage = ProgressStage.EXPLANATION_RECEIVED
            elif not source.technically_consistent:
                stage = ProgressStage.EVIDENCE_RECEIVED
            else:
                stage = ProgressStage.EVIDENCE_COHERENT
        elif explained and source is not None and source.officer_accepted and source.prior_raw_contribution is not None:
            selected = next(f for f in family_findings if f.status is FindingStatus.EXPLAINED)
            raw = Decimal(source.prior_raw_contribution)
            stage = ProgressStage.RESOLVED
        else:
            continue

        refs = [r.source_record_id or r.document_id for r in selected.evidence_refs
                if r.source_record_id or r.document_id]
        if source is not None:
            refs.extend(x for x in (source.response_id, source.document_id, source.proposal_id) if x)
        reason = (source.contradiction_reason if source is not None else None) or selected.reason_code
        causes.append(CauseProgress(
            transaction_id=transaction_id, family=family,
            raw_contribution=_decimal_str(raw),
            current_contribution=_decimal_str(raw * FACTORS[stage]),
            stage=stage, provisional=stage not in (ProgressStage.UNRESOLVED, ProgressStage.RESOLVED),
            reason_code=reason, source_ids=tuple(dict.fromkeys(refs)),
        ))
    return tuple(causes)


def transaction_progress_index(causes: tuple[CauseProgress, ...], transaction_id: str) -> int | None:
    selected = [c for c in causes if c.transaction_id == transaction_id]
    if not selected:
        return None
    total = min(Decimal(100), sum((Decimal(c.current_contribution) for c in selected), Decimal(0)))
    rounded = int(total.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    if rounded == 0 and any(c.stage is not ProgressStage.RESOLVED for c in selected):
        return 1
    return rounded


def _decimal_str(value: Decimal) -> str:
    return format(value.normalize(), "f")
