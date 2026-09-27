"""Pure, explainable historical context index; never a documentary finding."""

from __future__ import annotations

from boussla.contracts import (CompanyHistorySignal, HistoricalFactor, HistoricalIndicator,
                               HistorySignalCode)

WEIGHTS: dict[HistorySignalCode, int] = {
    HistorySignalCode.ACTIVITY_GAP: 15,
    HistorySignalCode.LATE_DOCUMENT_ACTIVITY: 10,
    HistorySignalCode.REPEATED_INVOICE_CONFLICT: 25,
    HistorySignalCode.VOLUME_SPIKE: 10,
    HistorySignalCode.VOLUME_DROP: 10,
    HistorySignalCode.PAYMENT_PATTERN_CHANGE: 12,
    HistorySignalCode.COUNTERPARTY_CONCENTRATION_CHANGE: 10,
    HistorySignalCode.UNUSUAL_DEPOSIT_DELAY: 10,
    HistorySignalCode.UNUSUAL_AMOUNT_INCREASE: 10,
    HistorySignalCode.UNUSUAL_AMOUNT_DECREASE: 10,
    HistorySignalCode.NEW_SUPPLIER: 8,
    HistorySignalCode.UNUSUAL_SPLIT_PAYMENT: 12,
}


def calculate_historical_indicator(signals: tuple[CompanyHistorySignal, ...]) -> HistoricalIndicator:
    if not signals or not any(s.reason_code in WEIGHTS or s.reason_code is HistorySignalCode.NO_SIGNIFICANT_CHANGE
                              for s in signals):
        return HistoricalIndicator(status="INSUFFICIENT_DATA")
    by_code: dict[HistorySignalCode, list[CompanyHistorySignal]] = {}
    for signal in signals:
        if signal.reason_code in WEIGHTS:
            by_code.setdefault(signal.reason_code, []).append(signal)
    factors = tuple(HistoricalFactor(
        reason_code=code, contribution=WEIGHTS[code],
        source_signal_ids=tuple(sorted({s.signal_id for s in items})),
        explanation_fr=items[0].explanation_fr,
    ) for code, items in sorted(by_code.items(), key=lambda pair: pair[0].value))
    return HistoricalIndicator(index=min(100, sum(f.contribution for f in factors)),
                               status="AVAILABLE", factors=factors)
