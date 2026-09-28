"""Network signals describe canonical, scoped transactions only."""
from types import SimpleNamespace as Row

from boussla.network import _network_signals


def _facts(transactions, observations):
    return (("CASE-1", {"transaction": transactions, "invoice_observation": observations}),)


def _transaction(number, buyer="BUYER", seller="SELLER", observations=()):
    return Row(transaction_id=f"TX-{number}", buyer_company_id=buyer,
               seller_company_id=seller, invoice_observation_ids=observations)


def _observation(number, amount=100000):
    return Row(observation_id=f"OBS-{number}", currency="TND", gross_millimes=amount)


def test_repeated_amount_counts_transactions_once_despite_two_invoice_perspectives():
    transactions = [_transaction(number, observations=(f"OBS-{number}-B", f"OBS-{number}-S"))
                    for number in range(1, 4)]
    observations = [Row(observation_id=f"OBS-{number}-{side}", currency="TND", gross_millimes=100000)
                    for number in range(1, 4) for side in ("B", "S")]
    signals = _network_signals(_facts(transactions, observations))
    repeated = next(item for item in signals if item.kind == "REPEATED_AMOUNT")
    assert repeated.sample_size == 3
    assert repeated.source_ids == ("TX-1", "TX-2", "TX-3")
    assert "fraude" not in repeated.explanation_fr.lower()


def test_concentration_needs_four_transactions_and_three_quarters_share():
    transactions = [_transaction(number, seller="A" if number < 4 else "B") for number in range(1, 5)]
    signals = _network_signals(_facts(transactions, []))
    concentration = next(item for item in signals if item.kind == "SUPPLIER_CONCENTRATION")
    assert concentration.company_ids == ("BUYER", "A")
    assert concentration.sample_size == 4
    assert concentration.source_ids == ("TX-1", "TX-2", "TX-3")
    assert not _network_signals(_facts(transactions[:3], []))


def test_reciprocal_link_requires_recorded_transactions_in_both_directions():
    forward = _transaction(1, buyer="A", seller="B")
    backward = _transaction(2, buyer="B", seller="A")
    assert not _network_signals(_facts([forward], []))
    signals = _network_signals(_facts([forward, backward], []))
    assert len(signals) == 1
    assert signals[0].kind == "RECIPROCAL_LINK"
    assert signals[0].source_ids == ("TX-1", "TX-2")


def test_conflicting_invoice_amounts_do_not_create_repeat_signal():
    transactions = [_transaction(number, observations=(f"OBS-{number}-B", f"OBS-{number}-S"))
                    for number in range(1, 4)]
    observations = [Row(observation_id=f"OBS-{number}-{side}", currency="TND",
                        gross_millimes=100000 if side == "B" else 90000)
                    for number in range(1, 4) for side in ("B", "S")]
    assert not _network_signals(_facts(transactions, observations))
