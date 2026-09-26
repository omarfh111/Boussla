"""Pure comparison of declared, interpreted and calculated project context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from boussla.contracts import Mode, PurposeCategory
from boussla.context.duration import DEMO_SHORT_HORIZON_MAX_DAYS, calculate_duration_days, classify_horizon
from boussla.context.models import ContextInput, ContextInterpretation, HorizonBucket


class ContextConsistencyStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    INSUFFICIENT = "INSUFFICIENT"


class CorroborationStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"


class ContextReasonCode(str, Enum):
    DECLARED_HORIZON_DATE_CONFLICT = "DECLARED_HORIZON_DATE_CONFLICT"
    DECLARED_HORIZON_TEXT_CONFLICT = "DECLARED_HORIZON_TEXT_CONFLICT"
    INTERPRETED_HORIZON_DATE_CONFLICT = "INTERPRETED_HORIZON_DATE_CONFLICT"
    PURPOSE_CATEGORY_TEXT_CONFLICT = "PURPOSE_CATEGORY_TEXT_CONFLICT"
    PROJECT_DATES_MISSING = "PROJECT_DATES_MISSING"
    INVALID_PROJECT_DATE_ORDER = "INVALID_PROJECT_DATE_ORDER"
    LONG_HORIZON_STAGE_MISSING = "LONG_HORIZON_STAGE_MISSING"
    LONG_HORIZON_BENEFICIARY_MISSING = "LONG_HORIZON_BENEFICIARY_MISSING"
    LONG_HORIZON_REFERENCE_MISSING = "LONG_HORIZON_REFERENCE_MISSING"
    CONTEXT_AMBIGUOUS = "CONTEXT_AMBIGUOUS"


CONFLICT_REASONS = frozenset({
    ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT,
    ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT,
    ContextReasonCode.INTERPRETED_HORIZON_DATE_CONFLICT,
    ContextReasonCode.PURPOSE_CATEGORY_TEXT_CONFLICT,
})


@dataclass(frozen=True)
class ContextConsistencyResult:
    declared_horizon: HorizonBucket
    interpreted_horizon: HorizonBucket
    calculated_horizon: HorizonBucket
    declared_purpose_category: PurposeCategory
    interpreted_purpose_category: PurposeCategory
    duration_days: int | None
    status: ContextConsistencyStatus
    reason_codes: tuple[ContextReasonCode, ...]
    corroboration: CorroborationStatus = CorroborationStatus.NOT_ASSESSED


def _missing(value: str | None) -> bool:
    return value is None or not value.strip() or value.strip().upper() in {"UNKNOWN", "OTHER_OR_UNKNOWN"}


def evaluate_consistency(
    context: ContextInput, interpretation: ContextInterpretation, *,
    short_max_days: int = DEMO_SHORT_HORIZON_MAX_DAYS,
) -> ContextConsistencyResult:
    """Compare sources without choosing a truth or changing any canonical field."""
    reasons: list[ContextReasonCode] = []
    invalid_dates = False
    try:
        duration = calculate_duration_days(context.planned_start, context.planned_end)
    except ValueError:
        duration = None
        invalid_dates = True
        reasons.append(ContextReasonCode.INVALID_PROJECT_DATE_ORDER)
    if duration is None and not invalid_dates:
        reasons.append(ContextReasonCode.PROJECT_DATES_MISSING)
    calculated = classify_horizon(duration, short_max_days=short_max_days)
    declared = context.declared_horizon
    interpreted = interpretation.suggested_horizon

    if declared is not HorizonBucket.UNKNOWN and calculated is not HorizonBucket.UNKNOWN and declared is not calculated:
        reasons.append(ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT)
    if declared is not HorizonBucket.UNKNOWN and interpreted is not HorizonBucket.UNKNOWN and declared is not interpreted:
        reasons.append(ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT)
    if interpreted is not HorizonBucket.UNKNOWN and calculated is not HorizonBucket.UNKNOWN and interpreted is not calculated:
        reasons.append(ContextReasonCode.INTERPRETED_HORIZON_DATE_CONFLICT)
    if (context.purpose_category is not PurposeCategory.OTHER_OR_UNKNOWN
            and interpretation.suggested_purpose_category is not PurposeCategory.OTHER_OR_UNKNOWN
            and context.purpose_category is not interpretation.suggested_purpose_category):
        reasons.append(ContextReasonCode.PURPOSE_CATEGORY_TEXT_CONFLICT)

    longer = calculated is HorizonBucket.LONGER_HORIZON or (
        calculated is HorizonBucket.UNKNOWN and
        (declared is HorizonBucket.LONGER_HORIZON or interpreted is HorizonBucket.LONGER_HORIZON)
    )
    if longer:
        if _missing(context.stage):
            reasons.append(ContextReasonCode.LONG_HORIZON_STAGE_MISSING)
        if _missing(context.beneficiary_type):
            reasons.append(ContextReasonCode.LONG_HORIZON_BENEFICIARY_MISSING)
        if context.reference_expected and _missing(context.project_reference):
            reasons.append(ContextReasonCode.LONG_HORIZON_REFERENCE_MISSING)
    if (not context.purpose_text.strip()
            or (interpretation.mode is Mode.LIVE and interpretation.ambiguities)):
        reasons.append(ContextReasonCode.CONTEXT_AMBIGUOUS)

    if any(reason in CONFLICT_REASONS for reason in reasons):
        status = ContextConsistencyStatus.NEEDS_CLARIFICATION
    elif invalid_dates or duration is None:
        status = ContextConsistencyStatus.INSUFFICIENT
    elif reasons:
        status = ContextConsistencyStatus.NEEDS_CLARIFICATION
    else:
        status = ContextConsistencyStatus.CONSISTENT
    return ContextConsistencyResult(
        declared_horizon=declared, interpreted_horizon=interpreted,
        calculated_horizon=calculated,
        declared_purpose_category=context.purpose_category,
        interpreted_purpose_category=interpretation.suggested_purpose_category,
        duration_days=duration, status=status, reason_codes=tuple(reasons),
    )
