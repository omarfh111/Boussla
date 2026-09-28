"""Read-only sequential resolution impact using the frozen cause contributions."""
from __future__ import annotations

from decimal import Decimal

from boussla.contracts import ProgressStage, ScoreSnapshot
from boussla.review_progress import transaction_progress_index

RULE_VERSION = "resolution-impact-1"


def simulate_resolution(score: ScoreSnapshot, raw_transaction_indices: dict[str, int | None]) -> tuple[dict, ...]:
    """Return no suggestion if the supplied transaction baseline cannot reconstruct the live index."""
    if score.review_index is None:
        return ()
    causes = score.cause_progress
    if not causes:
        return ()
    tx_ids = set(raw_transaction_indices) | {cause.transaction_id for cause in causes}

    def index_after(resolved: set[str]) -> int | None:
        adjusted = tuple(cause.model_copy(update={"stage": ProgressStage.RESOLVED,
                                                  "current_contribution": "0", "provisional": False})
                         if cause.cause_id in resolved else cause for cause in causes)
        values = []
        for tx_id in tx_ids:
            value = (transaction_progress_index(adjusted, tx_id)
                     if any(cause.transaction_id == tx_id for cause in adjusted)
                     else raw_transaction_indices.get(tx_id))
            if value is not None:
                values.append(value)
        return max(values) if values else None

    if index_after(set()) != score.review_index:
        return ()
    candidates = sorted((cause for cause in causes if Decimal(cause.current_contribution) > 0),
                        key=lambda cause: (-Decimal(cause.current_contribution), cause.transaction_id,
                                           cause.family.value))
    out = []
    resolved: set[str] = set()
    before = score.review_index
    for step, cause in enumerate(candidates, 1):
        resolved.add(cause.cause_id)
        after = index_after(resolved)
        if after is None:
            return ()
        out.append({"step": step, "cause_id": cause.cause_id, "family": cause.family.value,
                    "transaction_id": cause.transaction_id, "before_index": before,
                    "after_index": after, "source_ids": cause.source_ids,
                    "case_version": score.case_version, "calculated_at": score.calculated_at,
                    "rule_version": RULE_VERSION, "hypothetical": True})
        before = after
    return tuple(out)
