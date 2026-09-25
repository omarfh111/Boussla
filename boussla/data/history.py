"""Small linked synthetic financial history built from one event ledger."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def _month(year: int, month: int, offset: int) -> tuple[int, int]:
    absolute = year * 12 + month - 1 + offset
    return absolute // 12, absolute % 12 + 1


def generate_linked_history(*, start_year: int = 2025, start_month: int = 9,
                            months: int = 12, events_per_month: int = 2) -> dict:
    """Produce one ledger and related invoice, cash and declared-total views.

    Delays and two-installment cases are explicit rules. This generator is
    deterministic and returns fictional records only. It does not imply live
    source coverage or produce labels about fraud.
    """
    if not 1 <= start_month <= 12 or not 1 <= months <= 24 or not 1 <= events_per_month <= 10:
        raise ValueError("invalid small-history size or start month")
    events = []
    invoice_views = []
    payment_views = []
    declaration_views = []
    sequence = 0
    for offset in range(months):
        year, month = _month(start_year, start_month, offset)
        period = f"{year:04d}-{month:02d}"
        days = monthrange(year, month)[1]
        net_total = 0
        tax_total = 0
        for position in range(events_per_month):
            sequence += 1
            issued = date(year, month, min(5 + position * 10, days))
            event_id = f"SYN-TX-{sequence:04d}"
            net = 1_000_000 + sequence * 25_000
            tax = net * 19 // 100
            gross = net + tax
            net_total += net
            tax_total += tax
            two_installments = sequence % 6 == 0
            event = {
                "transaction_id": event_id, "buyer_company_id": "SYN-BUYER",
                "seller_company_id": "SYN-SELLER", "invoice_number": f"SYN-FAC-{sequence:04d}",
                "issued_on": issued.isoformat(), "economic_period": period,
                "currency": "TND", "net_millimes": net, "tax_millimes": tax,
                "gross_millimes": gross,
                "payment_terms": "TWO_INSTALLMENTS" if two_installments else "FULL",
                "data_kind": "SYNTHETIC",
            }
            events.append(event)
            for perspective, origin in (("BUYER_RECEIVED", "SYN-BUYER-UPLOAD"),
                                        ("SELLER_ISSUED", "SYN-SELLER-REFERENCE")):
                invoice_views.append({
                    "observation_id": f"{event_id}-{perspective}",
                    "transaction_id": event_id, "perspective": perspective,
                    "origin_group_id": origin, "invoice_number": event["invoice_number"],
                    "issued_on": event["issued_on"], "available_at": (issued + timedelta(days=2)).isoformat(),
                    "currency": "TND", "net_millimes": net, "tax_millimes": tax,
                    "gross_millimes": gross, "data_kind": "SYNTHETIC",
                })
            installments = ((gross // 2, 5), (gross - gross // 2, 25)) if two_installments else ((gross, 5),)
            for installment_number, (amount, day_offset) in enumerate(installments, start=1):
                paid_on = issued + timedelta(days=day_offset)
                payment_views.append({
                    "payment_id": f"{event_id}-PAY-{installment_number}",
                    "transaction_id": event_id, "amount_millimes": amount,
                    "allocated_millimes": amount, "status": "SETTLED",
                    "occurred_on": paid_on.isoformat(),
                    "available_at": (paid_on + timedelta(days=1)).isoformat(),
                    "origin_group_id": "SYN-PAYMENT-RECORD", "data_kind": "SYNTHETIC",
                })
        declaration_views.append({
            "period": period, "company_id": "SYN-SELLER", "kind": "INVOICED_SALES",
            "net_millimes": net_total, "tax_millimes": tax_total,
            "available_at": date(*_month(year, month, 1), 15).isoformat(),
            "data_kind": "SYNTHETIC",
        })
        declaration_views.append({
            "period": period, "company_id": "SYN-BUYER", "kind": "INVOICED_PURCHASES",
            "net_millimes": net_total, "tax_millimes": tax_total,
            "available_at": date(*_month(year, month, 1), 15).isoformat(),
            "data_kind": "SYNTHETIC",
        })
    return {
        "events": events, "invoice_views": invoice_views,
        "payment_views": payment_views, "declaration_views": declaration_views,
    }


def views_as_of(history: dict, cutoff: date) -> dict:
    """Expose only source views available by an explicit date, never future facts."""
    if not isinstance(cutoff, date):
        raise TypeError("cutoff must be a date")
    return {
        name: [row for row in history[name] if date.fromisoformat(row["available_at"]) <= cutoff]
        for name in ("invoice_views", "payment_views", "declaration_views")
    }
