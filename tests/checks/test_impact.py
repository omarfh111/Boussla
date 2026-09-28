"""No-write impact simulation across transactions and unknown baselines."""
from datetime import datetime, timezone

from boussla.contracts import CauseProgress, ClarificationStatus, FindingFamily, ProgressStage, ScoreSnapshot
from boussla.impact import simulate_resolution


def snapshot():
    causes = tuple(CauseProgress(
        cause_id=f"CASE:T-{number}:{family.value}", transaction_id=f"T-{number}", family=family,
        raw_contribution=str(weight), current_contribution=str(weight), stage=ProgressStage.UNRESOLVED,
        provisional=False,
    ) for number, family, weight in ((1, FindingFamily.QUANTITY, 40),
                                     (2, FindingFamily.COUNTERPARTY, 30)))
    return ScoreSnapshot(
        company_id="C-1", case_version=7, cutoff=datetime.now(timezone.utc), method_id="TEST",
        rules_version="test-1", review_index=40, cause_progress=causes,
        evidence_coverage="100", coverage_complete=True, scope_note="Test",
        unresolved_distinct_transactions=2, clarification_status=ClarificationStatus.NOT_REQUESTED,
    )


def test_sequential_impact_respects_company_maximum_and_does_not_mutate_snapshot():
    source = snapshot()
    steps = simulate_resolution(source, {"T-1": 40, "T-2": 30})
    assert [(item["before_index"], item["after_index"]) for item in steps] == [(40, 30), (30, 0)]
    assert all(item["hypothetical"] and item["case_version"] == 7 for item in steps)
    assert source.review_index == 40 and [cause.current_contribution for cause in source.cause_progress] == ["40", "30"]


def test_inconsistent_baseline_has_no_displayable_impact():
    assert simulate_resolution(snapshot().model_copy(update={"review_index": 35}), {"T-1": 40, "T-2": 30}) == ()
