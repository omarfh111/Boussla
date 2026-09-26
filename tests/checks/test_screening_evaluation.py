"""Population outputs record review situations, never predicted outcomes."""

import json
from pathlib import Path

from boussla.data.screening_evaluation import (
    evaluate_screening_population, render_company_queue_csv,
)


ROOT = Path(__file__).resolve().parents[2]


def _evaluation():
    population = json.loads((ROOT / "boussla" / "data" / "fixtures"
                             / "screening_population.json").read_text(encoding="utf-8"))
    return population, evaluate_screening_population(population)


def test_committed_machine_outputs_are_reproducible():
    population, evaluation = _evaluation()
    assert evaluation == evaluate_screening_population(population)
    assert json.loads((ROOT / "results" / "company_screening_results.json").read_text(
        encoding="utf-8")) == evaluation
    assert (ROOT / "results" / "company_screening_queue.csv").read_text(
        encoding="utf-8") == render_company_queue_csv(evaluation)
    assert evaluation["company_count"] == 40
    assert evaluation["transaction_count"] == 480
    assert evaluation["review_index_distribution"] == {"0": 20, "35": 5, "40": 10, "null": 5}
    assert evaluation["coverage_evaluable_checks"] == 1195
    assert evaluation["coverage_known_applicable_checks"] == 1440


def test_known_review_situations_use_existing_score_semantics():
    _, evaluation = _evaluation()
    companies = {row["company_id"]: row for row in evaluation["companies"]}
    assert companies["SYN-C001"]["review_index"] == 0
    assert companies["SYN-C001"]["coverage_complete"]
    assert companies["SYN-C002"]["review_index"] == 40
    assert companies["SYN-C002"]["contributing_families"] == {"QUANTITY": 1}
    assert companies["SYN-C003"]["review_index"] == 35
    assert companies["SYN-C003"]["contributing_families"] == {"COUNTERPARTY": 1}
    assert companies["SYN-C004"]["review_index"] is None
    assert companies["SYN-C004"]["null_transactions"] == 12
    assert companies["SYN-C005"]["review_index"] == 0
    assert not companies["SYN-C005"]["coverage_complete"]
    assert companies["SYN-C006"]["review_index"] == 0
    assert companies["SYN-C007"]["review_index"] == 0
    assert companies["SYN-C007"]["evidence_coverage_percent"] == "66.67"
    assert companies["SYN-C008"]["review_index"] == 40
    assert companies["SYN-C008"]["unresolved_distinct_transactions"] == 2


def test_reallocation_revision_and_equal_amount_priority_examples():
    population, evaluation = _evaluation()
    source = {row["transaction_id"]: row for row in population["transactions"]}
    result = {row["transaction_id"]: row for row in evaluation["transactions"]}
    ids = ("SYN-C001-TX-01", "SYN-C002-TX-01", "SYN-C003-TX-01")
    assert {source[tx_id]["revisions"][-1]["invoice_observations"][0]["gross_millimes"]
            for tx_id in ids} == {1_190_000}
    assert [result[tx_id]["revisions"][-1]["score"]["review_index"]
            for tx_id in ids] == [0, 40, 35]
    revised = result["SYN-C006-TX-01"]["revisions"]
    assert [version["case_version"] for version in revised] == [1, 2]
    assert [version["score"]["review_index"] for version in revised] == [40, 0]
    partial = result["SYN-C005-TX-01"]["revisions"][-1]
    assert partial["findings"][1]["reason_code"] == "PARTIAL_OR_UNEXPLAINED_SETTLEMENT_STAGE"
    assert partial["findings"][1]["status"] == "INSUFFICIENT"
    assert partial["score"]["review_index"] == 0
    missing = result["SYN-C007-TX-01"]["revisions"][-1]
    assert missing["findings"][0]["status"] == "INSUFFICIENT"
    assert missing["score"]["review_index"] == 0
