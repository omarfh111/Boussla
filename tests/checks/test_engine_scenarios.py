"""End-to-end structured fixture checks without extraction or service state."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from boussla.checks import ChecksEngineV4
from boussla.contracts import (
    Allocation, ChecksEngine, Delivery, Document, FindingFamily, FindingStatus,
    IdentityMapping, InvoiceObservation, Payment, PaymentAllocation,
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


def test_engine_implements_contract_and_main_fixture_index():
    engine = ChecksEngineV4()
    assert isinstance(engine, ChecksEngine)
    findings = engine.evaluate_transaction(_inputs())
    assert [f.family for f in findings] == list(FindingFamily)
    assert [f.status for f in findings] == [FindingStatus.EXPLAINED,
                                           FindingStatus.EXPLAINED,
                                           FindingStatus.UNRESOLVED]
    score = engine.score_transaction(findings, set(FindingFamily))
    assert score.review_index == 40
    assert score.coverage_complete
    assert engine.aggregate_company([score]) == 40


def test_sensitivity_and_candidate_do_not_mutate_accepted_facts():
    inputs = _inputs()
    before = inputs.model_dump(mode="json")
    scenarios = ChecksEngineV4().run_scenarios(inputs, {
        "candidate_reallocation": {"P1": "1000", "P2": "1000"},
    })
    assert [s.outputs["residual_units"] for s in scenarios] == ["1000", "900", "0"]
    assert scenarios[-1].outputs["status"] == "CANDIDATE_UNACCEPTED"
    assert all(s.hypothetical and not s.changes_canonical_state for s in scenarios)
    assert inputs.model_dump(mode="json") == before
    assert ChecksEngineV4().evaluate_transaction(inputs)[2].quantity_difference == "1000"


def test_double_allocation_candidate_is_invalid():
    scenario = ChecksEngineV4().run_scenarios(_inputs(), {
        "candidate_reallocation": {"P1": "2000", "P2": "1000"},
    })[-1]
    assert scenario.outputs["status"] == "INVALID_BUDGET"


def test_incomplete_candidate_does_not_clear_original_assignment():
    scenario = ChecksEngineV4().run_scenarios(_inputs(), {
        "candidate_reallocation": {"P2": "1000"},
    })[-1]
    assert scenario.outputs["status"] == "INCOMPLETE_REALLOCATION"


def test_accepted_reallocation_is_recalculated_to_zero():
    inputs = _inputs()
    first = inputs.allocations[0].model_copy(update={"quantity": "1000"})
    second = first.model_copy(update={
        "allocation_id": "ALLOC-P2-V2", "target_project_id": "P2", "quantity": "1000",
        "source_refs": ("DOC-SECOND-PROJECT",),
    })
    revised = inputs.model_copy(update={"case_version": 2, "allocations": (first, second)})
    findings = ChecksEngineV4().evaluate_transaction(revised)
    assert findings[2].status is FindingStatus.EXPLAINED
    assert ChecksEngineV4().score_transaction(findings, set(FindingFamily)).review_index == 0


def test_margin_inputs_reject_float_and_duplicate_grid():
    with pytest.raises(ValueError):
        ChecksEngineV4().run_scenarios(_inputs(), {"quantity_margins": [0.1]})
    with pytest.raises(ValueError):
        ChecksEngineV4().run_scenarios(_inputs(), {"quantity_margins": ["0.10", "0.1"]})
