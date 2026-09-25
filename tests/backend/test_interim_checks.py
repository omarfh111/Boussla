"""Interim checks on the synthetic brick case (pack reference arithmetic)."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from boussla.contracts import (
    Allocation, BaselineKind, FindingFamily as Fam, FindingStatus as St, HypothesisStatus, PaymentStatus, TransactionInputs,
)
from boussla.interim_checks import InterimChecks, get_checks_engine
from boussla.seed import load_fixture_facts

ENGINE = InterimChecks()
ALL = {Fam.COUNTERPARTY, Fam.SETTLEMENT, Fam.QUANTITY}


def inputs(**over) -> TransactionInputs:
    f = load_fixture_facts()
    base = dict(case_id="CASE-BRICKS-001", company_id="DEMO-BAT", case_version=1,
                as_of=datetime(2026, 9, 25, tzinfo=timezone.utc), transaction=f["transaction"][0],
                invoice_observations=tuple(f["invoice_observation"]), payments=tuple(f["payment"]),
                payment_allocations=tuple(f["payment_allocation"]), identity_mappings=tuple(f["identity_mapping"]),
                allocations=tuple(f["allocation"]), quantity_references=tuple(f["quantity_reference"]),
                context_claims=tuple(f["context_claim"]), deliveries=tuple(f["delivery"]))
    base.update(over)
    return TransactionInputs(**base)


def by_family(findings):
    return {f.family: f for f in findings}


def reallocated():
    a = load_fixture_facts()["allocation"][0]
    return (a.model_copy(update={"quantity": "1000"}),
            a.model_copy(update={"allocation_id": "ALLOC-P2-V2", "target_project_id": "P2", "quantity": "1000"}))


def test_seed_case_quantity_unresolved_others_explained():
    f = by_family(ENGINE.evaluate_transaction(inputs()))
    assert f[Fam.COUNTERPARTY].status is St.EXPLAINED
    assert f[Fam.SETTLEMENT].status is St.EXPLAINED and f[Fam.SETTLEMENT].observed_difference_millimes == 0
    q = f[Fam.QUANTITY]
    assert q.status is St.UNRESOLVED and q.quantity_difference == "1000" and q.severity == "1"
    score = ENGINE.score_transaction(list(f.values()), ALL)
    assert score.review_index == 40 and score.coverage_complete


def test_reallocation_resolves_quantity_and_supports_hypothesis():
    i = inputs(allocations=reallocated())
    findings = ENGINE.evaluate_transaction(i)
    assert by_family(findings)[Fam.QUANTITY].status is St.EXPLAINED
    assert ENGINE.score_transaction(findings, ALL).review_index == 0
    hyp = {h.hypothesis_id: h for h in ENGINE.test_hypotheses(i, findings)}
    assert hyp["H-SECOND-PACKAGE"].status is HypothesisStatus.SUPPORTED


def test_double_allocation_overflow_is_flagged():
    a = load_fixture_facts()["allocation"][0]
    extra = a.model_copy(update={"allocation_id": "ALLOC-P2-X", "target_project_id": "P2", "quantity": "1000"})
    q = by_family(ENGINE.evaluate_transaction(inputs(allocations=(a, extra))))[Fam.QUANTITY]
    assert q.status is St.UNRESOLVED and q.reason_code == "ALLOCATION_EXCEEDS_INVOICED_QUANTITY"


def test_same_origin_copies_are_not_independent():
    obs = load_fixture_facts()["invoice_observation"]
    same = tuple(o.model_copy(update={"origin_group_id": "COMPANY-DEMO-BAT"}) for o in obs)
    c = by_family(ENGINE.evaluate_transaction(inputs(invoice_observations=same)))[Fam.COUNTERPARTY]
    assert c.status is St.INSUFFICIENT and c.reason_code == "COMMON_ORIGIN_NOT_INDEPENDENT"


def test_wrong_issuer_blocks_match():
    b, s = load_fixture_facts()["invoice_observation"]
    s2 = s.model_copy(update={"issuer_company_id": "DEMO-OTHER"})
    c = by_family(ENGINE.evaluate_transaction(inputs(invoice_observations=(b, s2))))[Fam.COUNTERPARTY]
    assert c.status is St.UNRESOLVED and c.reason_code == "IDENTIFIER_MISMATCH"


def test_initiated_payment_not_settled_and_part_payment_abstains():
    p = load_fixture_facts()["payment"][0]
    init = by_family(ENGINE.evaluate_transaction(inputs(payments=(p.model_copy(update={"status": PaymentStatus.INITIATED}),))))
    assert init[Fam.SETTLEMENT].status is St.INSUFFICIENT
    pa = load_fixture_facts()["payment_allocation"][0]
    part = by_family(ENGINE.evaluate_transaction(inputs(payment_allocations=(pa.model_copy(update={"allocated_millimes": 2000000}),))))
    assert part[Fam.SETTLEMENT].status is St.INSUFFICIENT and part[Fam.SETTLEMENT].severity is None


def test_missing_mapping_makes_settlement_unavailable():
    s = by_family(ENGINE.evaluate_transaction(inputs(identity_mappings=())))[Fam.SETTLEMENT]
    assert s.status is St.INSUFFICIENT and s.reason_code == "UNKNOWN_IDENTITY_MAPPING"


def test_estimate_baseline_gives_no_quantity_points():
    refs = tuple(r.model_copy(update={"baseline_kind": BaselineKind.CONSUMPTION_ESTIMATE}) for r in load_fixture_facts()["quantity_reference"])
    findings = ENGINE.evaluate_transaction(inputs(quantity_references=refs))
    q = by_family(findings)[Fam.QUANTITY]
    assert q.status is St.INSUFFICIENT and q.severity is None
    score = ENGINE.score_transaction(findings, ALL)
    assert score.review_index == 0 and not score.coverage_complete


def test_scenarios_are_hypothetical_and_do_not_mutate():
    i = inputs()
    before = i.model_dump()
    sc = ENGINE.run_scenarios(i, {})
    assert [Decimal(s.outputs["residual"]) for s in sc] == [Decimal(1000), Decimal(900)]
    assert all(s.hypothetical and not s.changes_canonical_state for s in sc)
    assert i.model_dump() == before


def test_wrong_unit_not_comparable():
    a = load_fixture_facts()["allocation"][0].model_copy(update={"unit": "palette"})
    q = by_family(ENGINE.evaluate_transaction(inputs(allocations=(a,))))[Fam.QUANTITY]
    assert q.status is St.INSUFFICIENT


def test_engine_selection_defaults_to_interim(monkeypatch):
    from boussla import interim_checks
    monkeypatch.setattr(interim_checks.importlib.util, "find_spec", lambda name: None)
    assert isinstance(get_checks_engine(), InterimChecks)
