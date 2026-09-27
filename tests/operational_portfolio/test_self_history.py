"""Self-relative history signals stay neutral and require covered baseline data."""

from datetime import timedelta

from boussla.data.operational_portfolio import AS_OF, FIXTURE, seed_portfolio, transaction_inputs
from boussla.history_signals import analyze_self_history


PORTFOLIO = seed_portfolio(FIXTURE)
COMPANY = "SYN-OP-001"
COVERAGE = {f"2025-{month:02d}": f"{COMPANY}-COVERAGE-{month}" for month in range(1, 5)}


def run(facts, coverage=COVERAGE):
    from datetime import datetime
    return analyze_self_history(facts, company_id=COMPANY,
                                as_of=datetime.fromisoformat(AS_OF), coverage=coverage)


def first_four():
    return list(transaction_inputs(PORTFOLIO, COMPANY)[:4])


def test_late_deposit_uses_own_baseline_not_only_absolute_threshold():
    facts = first_four()
    current = facts[-1]
    buyer, seller = current.invoice_observations
    buyer = buyer.model_copy(update={"available_at": buyer.available_at + timedelta(days=12)})
    facts[-1] = current.model_copy(update={"invoice_observations": (buyer, seller)})
    signal = next(s for s in run(facts) if s.reason_code == "UNUSUAL_DEPOSIT_DELAY")
    assert signal.period == "2025-04"
    assert signal.observed_value == "14" and signal.baseline_value == "2"
    assert buyer.document_id in signal.evidence_source_ids
    assert not signal.affects_review_index
    assert "UNUSUAL_DEPOSIT_DELAY" not in {s.reason_code for s in run(facts, {})}


def test_amount_change_and_new_supplier_use_company_history():
    facts = first_four()
    current = facts[-1]
    buyer, seller = current.invoice_observations
    buyer = buyer.model_copy(update={"gross_millimes": buyer.gross_millimes * 3})
    transaction = current.transaction.model_copy(update={"seller_company_id": f"{COMPANY}-NEW-SUPPLIER"})
    facts[-1] = current.model_copy(update={"transaction": transaction,
                                   "invoice_observations": (buyer, seller)})
    by_code = {s.reason_code: s for s in run(facts)}
    assert "UNUSUAL_AMOUNT_INCREASE" in by_code
    assert "NEW_SUPPLIER" in by_code
    assert by_code["NEW_SUPPLIER"].baseline_periods == ("2025-01", "2025-02", "2025-03")
    assert all(s.evidence_source_ids for s in by_code.values())


def test_amount_drop_requires_same_currency_baseline():
    facts = first_four()
    current = facts[-1]
    buyer, seller = current.invoice_observations
    buyer = buyer.model_copy(update={"gross_millimes": buyer.gross_millimes // 3})
    facts[-1] = current.model_copy(update={"invoice_observations": (buyer, seller)})
    assert "UNUSUAL_AMOUNT_DECREASE" in {s.reason_code for s in run(facts)}
    buyer = buyer.model_copy(update={"currency": "EUR"})
    facts[-1] = current.model_copy(update={"invoice_observations": (buyer, seller)})
    assert "UNUSUAL_AMOUNT_DECREASE" not in {s.reason_code for s in run(facts)}


def test_unusual_split_payment_is_not_inferred_from_missing_coverage():
    facts = first_four()
    current = facts[-1]
    payment = current.payments[0]
    allocation = current.payment_allocations[0]
    payments = tuple(payment.model_copy(update={"payment_id": f"{payment.payment_id}-{n}",
                                         "amount_millimes": 400000}) for n in range(3))
    allocations = tuple(allocation.model_copy(update={"payment_id": p.payment_id,
                                               "allocated_millimes": 400000}) for p in payments)
    facts[-1] = current.model_copy(update={"payments": payments, "payment_allocations": allocations})
    assert "UNUSUAL_SPLIT_PAYMENT" in {s.reason_code for s in run(facts)}
    assert "UNUSUAL_SPLIT_PAYMENT" not in {s.reason_code for s in run(facts, {})}


def test_repeated_invoice_conflict_remains_a_neutral_separate_signal():
    company = "SYN-OP-002"
    row = next(r for r in PORTFOLIO["enterprises"] if r["identity"]["company_id"] == company)
    from datetime import datetime
    signals = analyze_self_history(transaction_inputs(PORTFOLIO, company), company_id=company,
                                   as_of=datetime.fromisoformat(AS_OF),
                                   coverage={r["period"]: r["source_id"] for r in row["coverage"]})
    repeated = next(s for s in signals if s.reason_code == "REPEATED_INVOICE_CONFLICT")
    assert repeated.evidence_source_ids and not repeated.affects_review_index
