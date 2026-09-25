"""Scoped procurement allocation and conservation tests."""

import json
from datetime import datetime
from pathlib import Path

from boussla.checks import compare_quantity_allocations
from boussla.contracts import (
    Allocation, AllocationTarget, BaselineKind, Delivery, FindingStatus, InvoiceObservation,
    QuantityReference, Transaction, TransactionInputs,
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
        as_of=datetime.fromisoformat("2026-09-25T12:00:00+01:00"), transaction=transaction,
        invoice_observations=tuple(InvoiceObservation.model_validate(row)
                                   for row in _rows("invoice_observations.json")),
        allocations=tuple(Allocation.model_validate(row) for row in _rows("allocations.json")),
        quantity_references=tuple(QuantityReference.model_validate(row)
                                  for row in _rows("quantity_references.json")),
        deliveries=tuple(Delivery.model_validate(row) for row in _rows("deliveries.json")),
    )


def test_first_project_has_exact_1000_unit_excess():
    finding = compare_quantity_allocations(_inputs())
    assert finding.status is FindingStatus.UNRESOLVED
    assert finding.quantity_difference == "1000"
    assert finding.unit == "piece"
    assert finding.severity == "1"


def test_reallocation_replaces_original_and_resolves_gap():
    inputs = _inputs()
    first = inputs.allocations[0].model_copy(update={"quantity": "1000"})
    second = first.model_copy(update={
        "allocation_id": "ALLOC-P2-V2", "target_project_id": "P2", "quantity": "1000",
        "source_refs": ("DOC-SECOND-PROJECT",),
    })
    finding = compare_quantity_allocations(inputs.model_copy(update={"allocations": (first, second)}))
    assert finding.status is FindingStatus.EXPLAINED
    assert finding.quantity_difference == "0"
    assert finding.severity == "0"


def test_adding_second_allocation_without_replacement_fails_conservation():
    inputs = _inputs()
    second = inputs.allocations[0].model_copy(update={
        "allocation_id": "ALLOC-P2-V2", "target_project_id": "P2", "quantity": "1000",
    })
    finding = compare_quantity_allocations(inputs.model_copy(update={"allocations": (*inputs.allocations, second)}))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "ALLOCATION_CONSERVATION_FAILED"


def test_user_estimate_cannot_generate_quantity_points():
    inputs = _inputs()
    first = inputs.quantity_references[0].model_copy(update={"baseline_kind": BaselineKind.USER_ESTIMATE})
    finding = compare_quantity_allocations(inputs.model_copy(update={
        "quantity_references": (first, inputs.quantity_references[1]),
    }))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "PROCUREMENT_BASELINE_UNAVAILABLE"
    assert finding.severity is None


def test_missing_delivery_abstains():
    finding = compare_quantity_allocations(_inputs().model_copy(update={"deliveries": ()}))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "ELIGIBLE_RECEIPT_UNAVAILABLE"


def test_estimate_only_assignment_cannot_generate_points():
    inputs = _inputs()
    estimate = inputs.allocations[0].model_copy(update={"fact_kind": "USER_ESTIMATE"})
    finding = compare_quantity_allocations(inputs.model_copy(update={"allocations": (estimate,)}))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "ESTIMATE_ONLY_ALLOCATION"


def test_wrong_unit_reference_abstains():
    inputs = _inputs()
    first = inputs.quantity_references[0].model_copy(update={"unit": "tonne"})
    finding = compare_quantity_allocations(inputs.model_copy(update={
        "quantity_references": (first, inputs.quantity_references[1]),
    }))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "PROCUREMENT_BASELINE_UNAVAILABLE"


def test_warehouse_transfer_requires_separate_scope_rules():
    inputs = _inputs()
    transfer = inputs.allocations[0].model_copy(update={
        "allocation_id": "WAREHOUSE-TRANSFER", "target_type": AllocationTarget.WAREHOUSE,
        "target_project_id": None, "quantity": "0",
    })
    finding = compare_quantity_allocations(inputs.model_copy(update={
        "allocations": (*inputs.allocations, transfer),
    }))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "TRANSFER_SCOPE_UNSUPPORTED"


def test_duplicate_receipt_identifier_cannot_support_quantity_points():
    inputs = _inputs()
    half_receipt = inputs.deliveries[0].model_copy(update={"quantity": "1000"})
    finding = compare_quantity_allocations(inputs.model_copy(update={
        "deliveries": (half_receipt, half_receipt),
    }))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "DUPLICATE_RECEIPT_ID"
