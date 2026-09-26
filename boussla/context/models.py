"""Narrow context-only types; declarations are never overwritten by interpretation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum

from boussla.contracts import PurposeCategory


class HorizonBucket(str, Enum):
    SHORT_HORIZON = "SHORT_HORIZON"
    LONGER_HORIZON = "LONGER_HORIZON"
    UNKNOWN = "UNKNOWN"


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
