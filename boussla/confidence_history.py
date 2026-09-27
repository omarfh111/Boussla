"""Version/cutoff-consistent factor deltas for the officer audit view."""

from __future__ import annotations

from boussla.contracts import (ConfidenceFactorDelta, ConfidenceHistoryEntry,
                               OperationalConfidence)


def confidence_delta(before: OperationalConfidence, after: OperationalConfidence,
                     *, from_version: int, to_version: int) -> ConfidenceHistoryEntry | None:
    older = {factor.code: factor for factor in before.factors}
    newer = {factor.code: factor for factor in after.factors}
    deltas = []
    for code in sorted(set(older) | set(newer)):
        a, b = older.get(code), newer.get(code)
        if a == b:
            continue
        deltas.append(ConfidenceFactorDelta(
            code=code,
            before_contribution=a.weighted_contribution if a else None,
            after_contribution=b.weighted_contribution if b else None,
            before_numerator=a.numerator if a else None,
            before_denominator=a.denominator if a else None,
            after_numerator=b.numerator if b else None,
            after_denominator=b.denominator if b else None,
            source_ids=tuple(sorted(set((a.source_ids if a else ()) + (b.source_ids if b else ())))),
            reason_codes=tuple(sorted(set((a.reason_codes if a else ()) + (b.reason_codes if b else ()))))))
    if before.index == after.index and before.status == after.status and not deltas:
        return None
    return ConfidenceHistoryEntry(from_version=from_version, to_version=to_version,
                                  as_of=after.as_of, before_index=before.index, after_index=after.index,
                                  before_status=before.status, after_status=after.status,
                                  factor_deltas=tuple(deltas))
