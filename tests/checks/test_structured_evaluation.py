"""Recorded structured-input cases; no PDF or real-world detection claims."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from boussla.checks import ChecksEngineV4
from boussla.contracts import (
    AcquisitionChannel, Allocation, BaselineKind, Delivery, Document,
    FindingFamily, IdentityMapping, InvoiceObservation, Payment,
    PaymentAllocation, QuantityReference, Transaction, TransactionInputs,
)

OBSERVED = Path(__file__).resolve().parents[2] / "docs" / "build_lock" / "fixtures" / "observed"


def _rows(name):
    return json.loads((OBSERVED / name).read_text(encoding="utf-8"))


def _base():
    transaction = Transaction.model_validate({
        key: value for key, value in _rows("transactions.json")[0].items()
        if key in Transaction.model_fields
    })
    return TransactionInputs(
        case_id="CASE-BRICKS-001", company_id="DEMO-BAT", case_version=1,
        as_of=datetime.fromisoformat("2026-09-25T12:00:00+01:00"), transaction=transaction,
        invoice_observations=tuple(InvoiceObservation.model_validate(row)
                                   for row in _rows("invoice_observations.json")),
        payments=tuple(Payment.model_validate(row) for row in _rows("payments.json")),
        payment_allocations=tuple(PaymentAllocation.model_validate(row)
                                  for row in _rows("payment_allocations.json")),
        identity_mappings=tuple(IdentityMapping.model_validate(row)
                                for row in _rows("identity_mappings.json")),
        allocations=tuple(Allocation.model_validate(row) for row in _rows("allocations.json")),
        quantity_references=tuple(QuantityReference.model_validate(row)
                                  for row in _rows("quantity_references.json")),
        deliveries=tuple(Delivery.model_validate(row) for row in _rows("deliveries.json")),
        documents=tuple(Document.model_validate({
            key: value for key, value in row.items() if key in Document.model_fields
        }) for row in _rows("documents.json") if row["document_id"] in {"DOC-BUY-001", "DOC-SELL-001"}),
    )


def _variant(name):
    inputs = _base()
    buyer, seller = inputs.invoice_observations
    if name == "BRICKS_ALLOCATION":
        return inputs
    if name == "COUNTERPARTY_CONFLICT":
        buyer = buyer.model_copy(update={"gross_millimes": 5950000})
        return inputs.model_copy(update={"invoice_observations": (buyer, seller)})
    if name == "PART_PAYMENT":
        payment = inputs.payments[0].model_copy(update={"amount_millimes": 2380000})
        allocation = inputs.payment_allocations[0].model_copy(update={"allocated_millimes": 2380000})
        return inputs.model_copy(update={"payments": (payment,), "payment_allocations": (allocation,)})
    if name == "SAME_ORIGIN":
        seller = seller.model_copy(update={"origin_group_id": buyer.origin_group_id})
        seller_doc = inputs.documents[1].model_copy(update={
            "origin_group_id": buyer.origin_group_id,
            "acquisition_channel": AcquisitionChannel.COMPANY_UPLOAD,
        })
        return inputs.model_copy(update={"invoice_observations": (buyer, seller),
                                         "documents": (inputs.documents[0], seller_doc)})
    if name == "MISSING_SUPPLIER":
        return inputs.model_copy(update={"invoice_observations": (buyer,)})
    if name == "VALID_REALLOCATION":
        first = inputs.allocations[0].model_copy(update={"quantity": "1000"})
        second = first.model_copy(update={"allocation_id": "ALLOC-P2-V2",
                                          "target_project_id": "P2", "quantity": "1000"})
        return inputs.model_copy(update={"case_version": 2, "allocations": (first, second)})
    if name == "USER_ESTIMATE":
        reference = inputs.quantity_references[0].model_copy(update={
            "baseline_kind": BaselineKind.USER_ESTIMATE,
        })
        return inputs.model_copy(update={"quantity_references": (reference, inputs.quantity_references[1])})
    if name == "WRONG_COMPANY":
        seller = seller.model_copy(update={"buyer_company_id": "OTHER-COMPANY"})
        return inputs.model_copy(update={"invoice_observations": (buyer, seller)})
    if name == "DOUBLE_ALLOCATION":
        second = inputs.allocations[0].model_copy(update={
            "allocation_id": "ALLOC-P2-V2", "target_project_id": "P2", "quantity": "1000",
        })
        return inputs.model_copy(update={"allocations": (*inputs.allocations, second)})
    if name == "MISSING_DELIVERY":
        return inputs.model_copy(update={"deliveries": ()})
    if name == "LINE_CONFLICT":
        line = seller.lines[0].model_copy(update={"quantity": "1500"})
        seller = seller.model_copy(update={"lines": (line,)})
        return inputs.model_copy(update={"invoice_observations": (buyer, seller)})
    if name == "WRONG_UNIT":
        reference = inputs.quantity_references[0].model_copy(update={"unit": "tonne"})
        return inputs.model_copy(update={"quantity_references": (reference, inputs.quantity_references[1])})
    if name == "UNCONFIRMED_FIELDS":
        buyer = buyer.model_copy(update={"transcription_status": "PROPOSED"})
        return inputs.model_copy(update={"invoice_observations": (buyer, seller)})
    raise ValueError(name)


CASES = [
    ("BRICKS_ALLOCATION", ("EXPLAINED", "EXPLAINED", "UNRESOLVED"), 40),
    ("COUNTERPARTY_CONFLICT", ("UNRESOLVED", "INSUFFICIENT", "UNRESOLVED"), 75),
    ("PART_PAYMENT", ("EXPLAINED", "INSUFFICIENT", "UNRESOLVED"), 40),
    ("SAME_ORIGIN", ("INSUFFICIENT", "EXPLAINED", "UNRESOLVED"), 40),
    ("MISSING_SUPPLIER", ("INSUFFICIENT", "EXPLAINED", "UNRESOLVED"), 40),
    ("VALID_REALLOCATION", ("EXPLAINED", "EXPLAINED", "EXPLAINED"), 0),
    ("USER_ESTIMATE", ("EXPLAINED", "EXPLAINED", "INSUFFICIENT"), 0),
    ("WRONG_COMPANY", ("INSUFFICIENT", "EXPLAINED", "UNRESOLVED"), 40),
    ("DOUBLE_ALLOCATION", ("EXPLAINED", "EXPLAINED", "INSUFFICIENT"), 0),
    ("MISSING_DELIVERY", ("EXPLAINED", "EXPLAINED", "INSUFFICIENT"), 0),
    ("LINE_CONFLICT", ("UNRESOLVED", "EXPLAINED", "UNRESOLVED"), 75),
    ("WRONG_UNIT", ("EXPLAINED", "EXPLAINED", "INSUFFICIENT"), 0),
    ("UNCONFIRMED_FIELDS", ("INSUFFICIENT", "INSUFFICIENT", "INSUFFICIENT"), None),
]


@pytest.mark.parametrize("name,statuses,index", CASES)
def test_structured_case(name, statuses, index):
    inputs = _variant(name)
    engine = ChecksEngineV4()
    findings = engine.evaluate_transaction(inputs)
    score = engine.score_transaction(findings, set(FindingFamily))
    assert tuple(f.status.value for f in findings) == statuses
    assert score.review_index == index
    assert all(f.case_version == inputs.case_version for f in findings)
