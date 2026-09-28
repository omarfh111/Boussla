"""Historical review context is explainable, bounded and never a finding."""

from boussla.contracts import CompanyHistorySignal, HistorySignalCode, Mode
from boussla.historical_indicator import calculate_historical_indicator


def signal(code: HistorySignalCode, suffix: str = "1") -> CompanyHistorySignal:
    return CompanyHistorySignal(
        signal_id=f"SIG-{suffix}", company_id="SYN-OP-001", reason_code=code,
        period="2025-12", metric="transaction_count", observed_value="3",
        baseline_value="1", baseline_periods=("2025-09", "2025-10", "2025-11"),
        evidence_source_ids=(f"SYN-OP-001-SOURCE-{suffix}",), explanation_fr="Variation à contextualiser.",
        method="SYNTHETIC_SELF_HISTORY_V2", mode=Mode.LIVE)


def test_no_covered_history_is_unknown_not_zero():
    result = calculate_historical_indicator((signal(HistorySignalCode.INSUFFICIENT_HISTORY),))
    assert result.index is None and result.status == "INSUFFICIENT_DATA"
    assert result.factors == ()


def test_covered_history_without_deviation_is_zero_context_signal():
    result = calculate_historical_indicator((signal(HistorySignalCode.NO_SIGNIFICANT_CHANGE),))
    assert result.index == 0 and result.status == "AVAILABLE"


def test_contributions_are_explicit_deduplicated_and_bounded():
    inputs = (signal(HistorySignalCode.UNUSUAL_DEPOSIT_DELAY, "delay-1"),
              signal(HistorySignalCode.UNUSUAL_DEPOSIT_DELAY, "delay-2"),
              signal(HistorySignalCode.REPEATED_INVOICE_CONFLICT, "conflict"))
    result = calculate_historical_indicator(inputs)
    assert result.index == 35
    assert {f.reason_code for f in result.factors} == {
        HistorySignalCode.UNUSUAL_DEPOSIT_DELAY, HistorySignalCode.REPEATED_INVOICE_CONFLICT}
    delay = next(f for f in result.factors if f.reason_code is HistorySignalCode.UNUSUAL_DEPOSIT_DELAY)
    assert delay.contribution == 10
    assert delay.source_signal_ids == ("SIG-delay-1", "SIG-delay-2")
    assert all(not s.affects_review_index for s in inputs)


def test_isolated_late_activity_without_own_company_baseline_has_no_index():
    isolated = signal(HistorySignalCode.LATE_DOCUMENT_ACTIVITY)
    isolated = isolated.model_copy(update={"baseline_periods": ()})
    result = calculate_historical_indicator((isolated,))
    assert result.status == "INSUFFICIENT_DATA"
    assert result.index is None
    assert result.factors == ()
