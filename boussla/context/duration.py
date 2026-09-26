"""Pure date arithmetic for the BOUSSLA demo horizon convention."""

from __future__ import annotations

from datetime import date

from boussla.context.models import HorizonBucket


DEMO_SHORT_HORIZON_MAX_DAYS = 90


def calculate_duration_days(planned_start: date | None, planned_end: date | None) -> int | None:
    if planned_start is None or planned_end is None:
        return None
    duration = (planned_end - planned_start).days
    if duration < 0:
        raise ValueError("planned end is before planned start")
    return duration


def classify_horizon(
    duration_days: int | None, *, short_max_days: int = DEMO_SHORT_HORIZON_MAX_DAYS,
) -> HorizonBucket:
    if short_max_days < 0:
        raise ValueError("short-horizon threshold must be nonnegative")
    if duration_days is None:
        return HorizonBucket.UNKNOWN
    if duration_days < 0:
        raise ValueError("duration cannot be negative")
    return (HorizonBucket.SHORT_HORIZON if duration_days <= short_max_days
            else HorizonBucket.LONGER_HORIZON)
