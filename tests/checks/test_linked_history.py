"""Synthetic history derives every view from one event ledger."""

from collections import defaultdict
from datetime import date
import json
from pathlib import Path

from boussla.data import generate_linked_history, views_as_of


def test_one_ledger_generates_consistent_views_and_declarations():
    history = generate_linked_history()
    assert len(history["events"]) == 24
    assert len(history["invoice_views"]) == 48
    assert len(history["declaration_views"]) == 24
    events = {event["transaction_id"]: event for event in history["events"]}
    invoices = defaultdict(list)
    payments = defaultdict(list)
    for view in history["invoice_views"]:
        invoices[view["transaction_id"]].append(view)
    for view in history["payment_views"]:
        payments[view["transaction_id"]].append(view)
    for event_id, event in events.items():
        assert {row["perspective"] for row in invoices[event_id]} == {"BUYER_RECEIVED", "SELLER_ISSUED"}
        assert all(row["gross_millimes"] == event["gross_millimes"] for row in invoices[event_id])
        assert sum(row["allocated_millimes"] for row in payments[event_id]) == event["gross_millimes"]
        assert all(row["status"] == "SETTLED" for row in payments[event_id])
    for declaration in history["declaration_views"]:
        period_events = [event for event in events.values()
                         if event["economic_period"] == declaration["period"]]
        assert declaration["net_millimes"] == sum(event["net_millimes"] for event in period_events)
        assert declaration["tax_millimes"] == sum(event["tax_millimes"] for event in period_events)


def test_part_installment_and_future_views_are_not_filled_in_early():
    history = generate_linked_history()
    event = history["events"][5]
    assert event["payment_terms"] == "TWO_INSTALLMENTS"
    installment_rows = [row for row in history["payment_views"]
                        if row["transaction_id"] == event["transaction_id"]]
    first_cutoff = date.fromisoformat(installment_rows[0]["available_at"])
    visible = views_as_of(history, first_cutoff)
    visible_installments = [row for row in visible["payment_views"]
                            if row["transaction_id"] == event["transaction_id"]]
    assert len(visible_installments) == 1
    assert visible_installments[0]["amount_millimes"] < event["gross_millimes"]
    assert all(date.fromisoformat(row["available_at"]) <= first_cutoff
               for rows in visible.values() for row in rows)


def test_generation_is_repeatable_and_size_is_bounded():
    assert generate_linked_history(months=2, events_per_month=1) == generate_linked_history(
        months=2, events_per_month=1)
    assert len(generate_linked_history(months=2, events_per_month=1)["events"]) == 2


def test_committed_history_matches_generator():
    path = Path(__file__).resolve().parents[2] / "boussla" / "data" / "fixtures" / "linked_history.json"
    assert json.loads(path.read_text(encoding="utf-8")) == generate_linked_history()
