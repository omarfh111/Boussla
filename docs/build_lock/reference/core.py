"""Small deterministic reference functions for the BOUSSLA build pack.

Not an application, fraud model, legal validator or document authenticator.
These demo policies are deliberately explicit and side-effect-free.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable, Mapping

D = Decimal
WEIGHTS = {"COUNTERPARTY": 35, "SETTLEMENT": 25, "QUANTITY": 40}


def decimal_value(value: str | int | Decimal) -> Decimal:
    if isinstance(value, (bool, float)):
        raise ValueError("Use decimal strings/integers, not booleans or binary floats")
    try:
        result = D(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("Non-finite decimal")
    return result


def to_millimes(amount_dt: str | Decimal) -> int:
    value = decimal_value(amount_dt) * 1000
    if value != value.to_integral_value():
        raise ValueError("More than three decimal places; choose explicit rounding first")
    return int(value)


def same_origin(origin_groups: Iterable[str]) -> bool:
    groups = list(origin_groups)
    if len(groups) < 2 or any(not item for item in groups):
        raise ValueError("At least two known origin groups are required")
    return len(set(groups)) == 1


def corroboration_status(origin_groups: Iterable[str]) -> str:
    groups = list(origin_groups)
    if len(groups) < 2 or any(not item for item in groups):
        return "ORIGIN_INSUFFICIENT"
    return "COMMON_ORIGIN" if same_origin(groups) else "DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY"


@dataclass(frozen=True)
class Finding:
    transaction_id: str
    family: str
    status: str
    severity: str | None
    evidence_ids: tuple[str, ...] = ()


def score_transaction(findings: Iterable[Finding], applicable_families: Iterable[str]) -> dict:
    """Demo weighted index; none evaluable => null; incomplete stays explicit.

    Caller supplies one transaction's findings and an explicit applicability set.
    No lateness, AI-origin, prior-score or company-reputation inputs exist.
    """
    applicable = set(applicable_families)
    if not applicable.issubset(WEIGHTS):
        raise ValueError("Unknown family")
    values: dict[str, Decimal] = {}
    txids: set[str] = set()
    for f in findings:
        txids.add(f.transaction_id)
        if f.family not in WEIGHTS or f.family not in applicable:
            raise ValueError("Finding outside declared applicable families")
        if f.status not in {"UNRESOLVED", "EXPLAINED", "INSUFFICIENT", "NOT_APPLICABLE"}:
            raise ValueError("Unknown status")
        if f.status in {"INSUFFICIENT", "NOT_APPLICABLE"}:
            if f.severity is not None:
                raise ValueError("Unknown/non-applicable is not observed zero severity")
            continue
        if f.severity is None or not f.evidence_ids:
            raise ValueError("Evaluable finding requires severity and evidence")
        s = decimal_value(f.severity)
        if not D(0) <= s <= D(1):
            raise ValueError("Severity outside [0,1]")
        if f.status == "EXPLAINED" and s != 0:
            raise ValueError("Explained finding cannot retain adverse severity")
        values[f.family] = max(values.get(f.family, D(0)), s)
    if len(txids) > 1:
        raise ValueError("Use one transaction per score call")
    coverage = (100 * D(len(values)) / len(applicable)) if applicable else None
    contributions = {family: str(D(WEIGHTS[family]) * s) for family, s in sorted(values.items())}
    total = sum((D(v) for v in contributions.values()), D(0))
    return {
        "review_index": int(total.quantize(D('1'), rounding=ROUND_HALF_UP)) if values else None,
        "evidence_coverage": str(coverage.quantize(D('0.01'))) if coverage is not None else None,
        "coverage_complete": bool(applicable) and set(values) == applicable,
        "evaluable_families": sorted(values),
        "unknown_families": sorted(applicable - set(values)),
        "contributions": contributions,
        "method": "CONTEXT_RULES_V4_1",
        "not_fraud_probability": True,
    }


def enterprise_index(transaction_scores: Iterable[Mapping]) -> int | None:
    values = [v['review_index'] for v in transaction_scores if v.get('review_index') is not None]
    return max(values) if values else None


def settlement_residual(payable_millimes: int | None, allocations: Iterable[Mapping],
                        *, mapping_confirmed: bool, comparable_terms: bool,
                        source_complete: bool) -> dict:
    """Compare known net payable with SETTLED allocations only.

    This simplified reference declines unsupported partial-payment terms.
    Full application must enforce allocation budgets and explicit adjustments.
    """
    if not (mapping_confirmed and comparable_terms and source_complete) or payable_millimes is None:
        return {"status": "INSUFFICIENT_INFORMATION", "residual_millimes": None}
    if isinstance(payable_millimes, bool) or not isinstance(payable_millimes, int) or payable_millimes < 0:
        raise ValueError("Nonnegative integer payable required")
    total = 0
    seen: dict[str, tuple] = {}
    for row in allocations:
        amount = row['allocated_millimes']
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("Nonnegative integer allocation required")
        key = row['allocation_id']
        signature = (amount, row['status'])
        if key in seen:
            if seen[key] != signature:
                raise ValueError("Conflicting duplicate allocation")
            continue
        seen[key] = signature
        if row['status'] == 'SETTLED':
            total += amount
        elif row['status'] not in {'INITIATED', 'REVERSED', 'UNKNOWN'}:
            raise ValueError("Unknown payment status")
    return {"status": "COMPARABLE", "settled_millimes": total,
            "residual_millimes": payable_millimes - total}


def quantity_excess(assigned: str, limit: str | None, *, baseline_kind: str,
                    reference_accepted: bool, units_match: bool, scope_match: bool) -> dict:
    if (limit is None or baseline_kind != 'APPROVED_PROCUREMENT_ALLOCATION'
        or not reference_accepted or not units_match or not scope_match):
        return {"status": "CONTEXT_ONLY_OR_INSUFFICIENT", "excess": None, "severity": None}
    a, q = decimal_value(assigned), decimal_value(limit)
    if a < 0 or q <= 0:
        raise ValueError("Nonnegative assigned and positive reference required")
    excess = max(D(0), a - q)
    severity = min(D(1), (excess / q) / D('0.50'))
    return {"status": "COMPARABLE", "excess": str(excess), "severity": str(severity)}


def allocation_budget(total_available: str, target_allocations: Mapping[str, str]) -> dict:
    total = decimal_value(total_available)
    values = {k: decimal_value(v) for k, v in target_allocations.items()}
    if total < 0 or any(v < 0 for v in values.values()):
        raise ValueError("Negative quantity")
    used = sum(values.values(), D(0))
    if used > total:
        raise ValueError("ALLOCATION_OVERFLOW")
    return {"used": str(used), "unallocated": str(total - used)}


def quantity_scenarios(assigned: str, baseline: str, margins: Iterable[str]) -> list[dict]:
    a, b = decimal_value(assigned), decimal_value(baseline)
    if a < 0 or b <= 0:
        raise ValueError("Invalid scenario quantities")
    results = []
    for margin in margins:
        m = decimal_value(margin)
        if m < 0:
            raise ValueError("Negative sensitivity margin")
        bound = b * (1 + m)
        results.append({"margin": str(m), "hypothetical_bound": str(bound),
                        "residual": str(max(D(0), a - bound)),
                        "hypothetical": True, "changes_canonical_state": False})
    return results


def follow_up_status(*, now: datetime, target: datetime | None,
                     request_approved: bool, available_to_company: bool,
                     service_available: bool, responded: bool,
                     extension_requested: bool, extended_target: datetime | None = None) -> str:
    """Administrative demo status only: intentionally no score side effect."""
    for value in (now, target, extended_target):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timezone-aware datetimes required")
    if responded:
        return 'RESPONSE_RECEIVED'
    if not request_approved:
        return 'NOT_REQUESTED'
    if not available_to_company or not service_available:
        return 'FOLLOW_UP_STATUS_UNKNOWN'
    if extension_requested and extended_target is None:
        return 'EXTENSION_REQUESTED'
    deadline = extended_target or target
    if deadline is None:
        return 'AWAITING_RESPONSE'
    if now > deadline:
        return 'FOLLOW_UP_DUE'
    return 'EXTENDED' if extended_target else 'AWAITING_RESPONSE'
