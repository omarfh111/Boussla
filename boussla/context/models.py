"""Narrow context-only types; declarations are never overwritten by interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from boussla.contracts import HorizonBucket, Mode, PurposeCategory  # HorizonBucket: single shared definition

__all__ = ["ContextInput", "ContextInterpretation", "HorizonBucket", "unknown_interpretation"]


@dataclass(frozen=True)
class ContextInput:
    purpose_category: PurposeCategory
    purpose_text: str
    planned_start: date | None
    planned_end: date | None
    stage: str | None
    beneficiary_type: str | None
    declared_horizon: HorizonBucket
    project_reference: str | None = None
    reference_expected: bool = False

    @classmethod
    def from_claim(
        cls, claim: object, *, declared_horizon: HorizonBucket,
        project_reference: str | None = None, reference_expected: bool = False,
    ) -> "ContextInput":
        """Copy only contextual fields from Lane A's richer ContextClaim."""
        return cls(
            purpose_category=PurposeCategory(getattr(claim, "purpose_category")),
            purpose_text=getattr(claim, "purpose_text"),
            planned_start=getattr(claim, "planned_start"),
            planned_end=getattr(claim, "planned_end"),
            stage=getattr(claim, "stage"),
            beneficiary_type=getattr(claim, "beneficiary_type"),
            declared_horizon=HorizonBucket(declared_horizon),
            project_reference=project_reference, reference_expected=reference_expected,
        )


@dataclass(frozen=True)
class ContextInterpretation:
    suggested_purpose_category: PurposeCategory
    suggested_horizon: HorizonBucket
    explicit_duration_text: str | None
    supporting_spans: tuple[str, ...]
    ambiguities: tuple[str, ...]
    model_id: str | None
    mode: Mode


def unknown_interpretation(mode: Mode, ambiguity: str) -> ContextInterpretation:
    return ContextInterpretation(
        suggested_purpose_category=PurposeCategory.OTHER_OR_UNKNOWN,
        suggested_horizon=HorizonBucket.UNKNOWN,
        explicit_duration_text=None, supporting_spans=(), ambiguities=(ambiguity,),
        model_id=None, mode=mode,
    )
