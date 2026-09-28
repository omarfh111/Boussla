"""Calendar monthly context; missing ledger coverage is never a zero observation."""

from __future__ import annotations

from datetime import date

from boussla.contracts import MonthlyActivityView


def build_monthly_context(months: dict[str, tuple[int, int, int]], coverage: dict[str, str],
                          end_month: str, *, count: int = 12) -> tuple[MonthlyActivityView, ...]:
    if count < 1:
        raise ValueError("count must be positive")
    end = date.fromisoformat(end_month + "-01")
    end_index = end.year * 12 + end.month - 1
    result = []
    for index in range(end_index - count + 1, end_index + 1):
        year, zero_month = divmod(index, 12)
        period = f"{year:04d}-{zero_month + 1:02d}"
        tx, invoice, outflow = months.get(period, (0, 0, 0))
        source = coverage.get(period) or None
        result.append(MonthlyActivityView(
            month=period, transaction_count=tx, invoice_observation_count=invoice,
            settled_outflow_millimes=outflow,
            coverage_status="COVERED" if source else "UNKNOWN", coverage_source_id=source,
            source_label="Période couverte par la source synthétique" if source
            else "Couverture du registre non attestée ; 0 ne signifie pas absence d’activité"))
    return tuple(result)
