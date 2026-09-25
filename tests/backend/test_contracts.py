"""Shape/validation tests for boussla.contracts (lane A)."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from boussla import CONTRACT_VERSION
from boussla.contracts import (
    Allocation, BousslaService, ChecksEngine, CompanyCaseView, ContextClaim, ErrorCode, BousslaError,
    InvoiceLine, InvoiceObservation, OfficerCaseView, Payment, QuantityReference, Scenario, ScoreSnapshot,
    Transaction,
)

FIX = Path(__file__).resolve().parents[2] / "docs" / "build_lock" / "fixtures" / "observed"


def load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_contract_version():
    assert CONTRACT_VERSION == "boussla-context-1"


@pytest.mark.parametrize("model,name,drop", [
    (InvoiceObservation, "invoice_observations.json", ()),
    (Payment, "payments.json", ()),
    (Allocation, "allocations.json", ()),
    (QuantityReference, "quantity_references.json", ()),
    (ContextClaim, "context_claims.json", ()),
    (Transaction, "transactions.json", ("synthetic",)),
])
def test_fixtures_validate(model, name, drop):
    for row in load(name):
        model(**{k: v for k, v in row.items() if k not in drop})


def test_money_rejects_float_and_bool():
    base = load("payments.json")[0]
    with pytest.raises(ValidationError):
        Payment(**{**base, "amount_millimes": 4760.0})
    with pytest.raises(ValidationError):
        Payment(**{**base, "amount_millimes": True})
    with pytest.raises(ValidationError):
        Payment(**{**base, "amount_millimes": -1})


def test_quantity_must_be_decimal_string():
    line = dict(line_id="L", item_description="x", quantity="2000", unit="piece",
                unit_price_millimes=1, line_net_millimes=1)
    InvoiceLine(**line)
    for bad in (2000.0, "abc", "NaN"):
        with pytest.raises(ValidationError):
            InvoiceLine(**{**line, "quantity": bad})


def test_naive_timestamp_rejected():
    base = load("payments.json")[0]
    with pytest.raises(ValidationError):
        Payment(**{**base, "occurred_at": "2026-09-07T12:00:00"})


def test_unknown_fields_and_mutation_rejected():
    base = load("payments.json")[0]
    with pytest.raises(ValidationError):
        Payment(**{**base, "fraud_probability": "0.9"})
    p = Payment(**base)
    with pytest.raises(ValidationError):
        p.amount_millimes = 1


def test_scenario_cannot_claim_canonical_change():
    with pytest.raises(ValidationError):
        Scenario(scenario_id="S", label="x", inputs={}, outputs={}, changes_canonical_state=True)


def test_company_view_has_no_internal_fields():
    internal = {"findings", "score", "hypotheses", "scenarios", "proposals", "candidate_passages", "quantity_references"}
    assert not internal & set(CompanyCaseView.model_fields)
    assert internal <= set(OfficerCaseView.model_fields)
    assert "review_index" in ScoreSnapshot.model_fields


def test_error_carries_code():
    err = BousslaError(ErrorCode.STALE_REVISION, "x", current=3)
    assert err.code is ErrorCode.STALE_REVISION and err.details == {"current": 3}


def test_protocols_are_runtime_checkable():
    assert not isinstance(object(), BousslaService)
    assert not isinstance(object(), ChecksEngine)
