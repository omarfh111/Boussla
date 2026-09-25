"""Settlement evidence must be explicit and installment safe."""

import json
from datetime import datetime
from pathlib import Path

from boussla.checks import reconcile_settlements
from boussla.contracts import (
    FindingStatus, IdentityMapping, InvoiceObservation, Payment,
    PaymentAllocation, PaymentStatus, Transaction, TransactionInputs,
)

OBSERVED = Path(__file__).resolve().parents[2] / "docs" / "build_lock" / "fixtures" / "observed"


def _rows(name):
    return json.loads((OBSERVED / name).read_text(encoding="utf-8"))


def _inputs():
    transaction = Transaction.model_validate({
        key: value for key, value in _rows("transactions.json")[0].items()
        if key in Transaction.model_fields
    })
    return TransactionInputs(
        case_id="CASE-BRICKS-001", company_id="DEMO-BAT", case_version=1,
        as_of=datetime.fromisoformat("2026-09-25T12:00:00+01:00"),
        transaction=transaction,
        invoice_observations=tuple(InvoiceObservation.model_validate(row)
                                   for row in _rows("invoice_observations.json")),
        payments=tuple(Payment.model_validate(row) for row in _rows("payments.json")),
        payment_allocations=tuple(PaymentAllocation.model_validate(row)
                                  for row in _rows("payment_allocations.json")),
        identity_mappings=tuple(IdentityMapping.model_validate(row)
                                for row in _rows("identity_mappings.json")),
    )


def test_exact_documented_settlement_matches_payable():
    finding = reconcile_settlements(_inputs())
    assert finding.status is FindingStatus.EXPLAINED
    assert finding.severity == "0"
    assert {ref.source_record_id for ref in finding.evidence_refs if ref.source_record_id} == {"DOC-PAY-001"}


def test_part_payment_abstains_without_due_schedule():
    inputs = _inputs()
    payment = inputs.payments[0].model_copy(update={"amount_millimes": 2380000})
    allocation = inputs.payment_allocations[0].model_copy(update={"allocated_millimes": 2380000})
    inputs = inputs.model_copy(update={"payments": (payment,), "payment_allocations": (allocation,)})
    finding = reconcile_settlements(inputs)
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "PARTIAL_OR_UNEXPLAINED_SETTLEMENT_STAGE"
    assert finding.observed_difference_millimes is None
    assert finding.severity is None


def test_missing_mapping_prevents_payment_claim():
    inputs = _inputs().model_copy(update={"identity_mappings": ()})
    finding = reconcile_settlements(inputs)
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "PAYMENT_IDENTITY_UNVERIFIED"


def test_initiated_payment_is_not_settled_cash():
    inputs = _inputs()
    payment = inputs.payments[0].model_copy(update={"status": PaymentStatus.INITIATED})
    finding = reconcile_settlements(inputs.model_copy(update={"payments": (payment,)}))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "INCOMPARABLE_PAYMENT"


def test_allocation_cannot_exceed_source_payment():
    inputs = _inputs()
    payment = inputs.payments[0].model_copy(update={"amount_millimes": 1000000})
    finding = reconcile_settlements(inputs.model_copy(update={"payments": (payment,)}))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "INCOMPARABLE_PAYMENT"
