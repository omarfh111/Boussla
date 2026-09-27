"""Twelve calendar months distinguish covered zero from unknown coverage."""

from boussla.monthly_context import build_monthly_context


def test_calendar_window_keeps_zero_and_unknown_months_distinct():
    months = {"2025-01": (1, 2, 1000)}
    coverage = {"2025-01": "COV-JAN", "2025-02": "COV-FEB"}
    result = build_monthly_context(months, coverage, "2025-03", count=3)
    assert [m.month for m in result] == ["2025-01", "2025-02", "2025-03"]
    assert [(m.transaction_count, m.coverage_status, m.coverage_source_id) for m in result] == [
        (1, "COVERED", "COV-JAN"), (0, "COVERED", "COV-FEB"), (0, "UNKNOWN", None)]


def test_exact_twelve_calendar_months_cross_year_boundary():
    result = build_monthly_context({}, {}, "2025-01")
    assert len(result) == 12
    assert result[0].month == "2024-02" and result[-1].month == "2025-01"
    assert all(m.coverage_status == "UNKNOWN" for m in result)
