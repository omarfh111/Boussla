"""The committed population is deterministic and keeps source views linked."""

import json
from collections import Counter
from pathlib import Path

from boussla.contracts import TransactionInputs
from boussla.data.screening_population import generate_screening_population


FIXTURE = (Path(__file__).resolve().parents[2] / "boussla" / "data" / "fixtures"
           / "screening_population.json")


def test_population_size_seed_and_committed_fixture():
    population = generate_screening_population()
    assert population == generate_screening_population()
    assert population != generate_screening_population(seed=1)
    assert json.loads(FIXTURE.read_text(encoding="utf-8")) == population
    assert len(population["companies"]) == 40
    assert len(population["transactions"]) == 480
    assert len(population["monthly_history"]) == 480
    assert Counter(row["company_id"] for row in population["transactions"]) == {
        company["company_id"]: 12 for company in population["companies"]
    }
    assert "fraud" not in json.dumps(population).lower()
    assert all(row["declared_total_millimes"] is None
               for row in population["monthly_history"])


def test_source_links_and_reallocation_history():
    population = generate_screening_population()
    assert sum(len(row["revisions"]) == 2 for row in population["transactions"]) == 5
    for row in population["transactions"]:
        for revision in row["revisions"]:
            inputs = TransactionInputs.model_validate(revision)
            assert inputs.company_id == row["company_id"]
            assert inputs.transaction.transaction_id == row["transaction_id"]
            assert {o.observation_id for o in inputs.invoice_observations} == set(
                inputs.transaction.invoice_observation_ids)
            assert all(o.document_id in {d.document_id for d in inputs.documents}
                       for o in inputs.invoice_observations)
            assert all(a.payment_id in {p.payment_id for p in inputs.payments}
                       for a in inputs.payment_allocations)
            assert all(a.line_id == inputs.invoice_observations[0].lines[0].line_id
                       for a in inputs.allocations)
    assert all(c["data_kind"] == "SYNTHETIC" for c in population["companies"])
    by_transaction = {row["transaction_id"]: row["revisions"][-1]
                      for row in population["transactions"]}
    for month in population["monthly_history"]:
        event = by_transaction[month["transaction_ids"][0]]
        assert month["invoiced_purchases_millimes"] == event["invoice_observations"][0]["gross_millimes"]
        assert month["observed_settled_millimes"] == sum(
            allocation["allocated_millimes"] for allocation in event.get("payment_allocations", []))
