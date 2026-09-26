from copy import deepcopy
from datetime import date
import json

import pytest

from boussla.checks import ChecksEngineV4
from boussla.contracts import Enterprise, FindingFamily
from boussla.data.operational_portfolio import (
    FIXTURE, add_synthetic_enterprise, case_facts, delete_synthetic_enterprise, enterprise_facts,
    generate_operational_portfolio, list_enterprises, reset_portfolio, seed_portfolio, transaction_inputs,
)


@pytest.fixture(scope="module")
def portfolio():
    return seed_portfolio(FIXTURE)


def test_deterministic_fixture_and_no_runtime_oracle(portfolio):
    assert portfolio == generate_operational_portfolio() == seed_portfolio()
    serialized = json.dumps(portfolio).lower()
    for forbidden in ("expected", "evaluation_only", "archetype", "fraud", "review_index", "risk_label"):
        assert forbidden not in serialized
    assert len(list_enterprises(portfolio)) == 12
    assert sum(len(r["events"]) for r in portfolio["enterprises"]) == 147
    for row in portfolio["enterprises"]:
        assert 8 <= len(row["events"]) <= 15
        assert len(row["coverage"]) == 12
        assert row["history_start"] == "2025-01" and row["history_end"] == "2025-12"


@pytest.mark.parametrize("number", range(1,13))
def test_linked_views_sources_and_current_checks(portfolio, number):
    cid = f"SYN-OP-{number:03d}"
    row = enterprise_facts(portfolio, cid)
    engine = ChecksEngineV4()
    known_sources = {r["source_id"] for r in row["source_records"]}
    txs = transaction_inputs(portfolio, cid)
    for i in txs:
        assert len(engine.evaluate_transaction(i)) == 3
        engine.score_transaction(engine.evaluate_transaction(i), set(FindingFamily))
        buyer = i.invoice_observations[0]
        assert buyer.buyer_mf_raw == row["identity"]["synthetic_mf"]
        assert sum(p.amount_millimes for p in i.payments) <= buyer.gross_millimes
        for o in i.invoice_observations:
            assert o.transaction_id == i.transaction.transaction_id
            assert o.buyer_company_id == cid
            assert o.issuer_company_id == i.transaction.seller_company_id
            assert o.gross_millimes == o.net_millimes + o.tax_millimes
        if len(i.invoice_observations) == 2:
            seller = i.invoice_observations[1]
            for field in ("invoice_number", "invoice_version", "issued_on", "buyer_company_id", "issuer_company_id", "currency"):
                assert getattr(buyer, field) == getattr(seller, field)
            assert buyer.document_id != seller.document_id
            assert buyer.origin_group_id != seller.origin_group_id
            assert i.documents[0].uploader_actor_id != i.documents[1].uploader_actor_id
            assert i.documents[1].acquisition_channel.value == "SIMULATED_COUNTERPARTY_REFERENCE"
        for record in (*i.allocations, *i.quantity_references, *i.deliveries):
            assert set(record.source_refs) <= known_sources
        for payment in i.payments:
            assert payment.source_record_id in known_sources
    assert len(case_facts(portfolio,cid)["transaction"]) == len(txs)


def test_pairs_and_no_project_assets(portfolio):
    pairs = sum(len(i.invoice_observations) == 2 for e in list_enterprises(portfolio)
                for i in transaction_inputs(portfolio,e.company_id))
    assert pairs == 135
    for number in (4,7,8,11):
        cid = f"SYN-OP-{number:03d}"
        for i in transaction_inputs(portfolio,cid):
            assert i.transaction.project_id is None
            assert all(line.project_id is None for o in i.invoice_observations for line in o.lines)
            assert i.context_claims[0].purpose_category.value == "LONG_LIVED_ASSET"
        assert not case_facts(portfolio,cid)["project"]


def test_copy_on_write_management(portfolio):
    original = deepcopy(portfolio)
    reduced = delete_synthetic_enterprise(portfolio,"SYN-OP-001")
    assert len(list_enterprises(reduced)) == 11
    restored = add_synthetic_enterprise(reduced, enterprise_facts(portfolio,"SYN-OP-001"))
    assert len(list_enterprises(restored)) == 12
    with pytest.raises(ValueError):
        add_synthetic_enterprise(portfolio, enterprise_facts(portfolio,"SYN-OP-001"))
    with pytest.raises(KeyError):
        enterprise_facts(portfolio,"UNKNOWN")
    with pytest.raises(KeyError):
        delete_synthetic_enterprise(portfolio,"UNKNOWN")
    new = Enterprise(company_id="SYN-NEW", synthetic_mf="SYNTHETIC-NEW", display_name="SYNTHETIC New",
                     sector="Synthetic", created_on=date(2025,1,1))
    extended = add_synthetic_enterprise(portfolio,new)
    assert not enterprise_facts(extended,"SYN-NEW")["events"]
    assert reset_portfolio(extended) == original == portfolio
    scoped = enterprise_facts(portfolio,"SYN-OP-001")
    scoped["identity"]["display_name"] = "edited"
    assert portfolio == original


@pytest.mark.parametrize("field", ["company", "invoice", "payment", "document", "context", "project", "source", "oracle", "snapshot"])
def test_reject_cross_company_and_extra_data(portfolio, field):
    row = enterprise_facts(portfolio,"SYN-OP-001")
    i = row["events"][0]["inputs"]
    if field == "company": i["company_id"] = "SYN-OP-002"
    elif field == "invoice": i["invoice_observations"][0]["buyer_company_id"] = "SYN-OP-002"
    elif field == "payment": i["payments"][0]["payer_company_id"] = "SYN-OP-002"
    elif field == "document": i["documents"][0]["subject_company_id"] = "SYN-OP-002"
    elif field == "context": i["context_claims"][0]["company_id"] = "SYN-OP-002"
    elif field == "project": row["events"][0]["projects"][0]["company_id"] = "SYN-OP-002"
    elif field == "source": row["source_records"][0]["company_id"] = "SYN-OP-002"
    elif field == "oracle": row["expected_answer"] = 0
    else: row["synthetic_authorized_financial_snapshot"]["observed_outflows_millimes"] = 0
    with pytest.raises(ValueError):
        add_synthetic_enterprise(delete_synthetic_enterprise(portfolio,"SYN-OP-001"),row)


def test_financial_snapshot_reversals_credit_notes_and_no_double_count(portfolio):
    for row in portfolio["enterprises"]:
        snapshot = row["synthetic_authorized_financial_snapshot"]
        assert snapshot["data_kind"] == "SYNTHETIC"
        assert snapshot["observed_inflows_millimes"] == 0
        assert snapshot["documented_payable_millimes"] == sum(
            e["inputs"]["invoice_observations"][0]["gross_millimes"] +
            sum(a["signed_millimes"] for a in e["inputs"]["settlement_adjustments"]) for e in row["events"])
    txs = transaction_inputs(portfolio,"SYN-OP-011")
    assert txs[-2].settlement_adjustments[0].signed_millimes < 0
    findings = ChecksEngineV4().evaluate_transaction(txs[-2])
    assert next(f for f in findings if f.family is FindingFamily.SETTLEMENT).status.value == "EXPLAINED"
    assert txs[-1].payments[0].status.value == "REVERSED"
