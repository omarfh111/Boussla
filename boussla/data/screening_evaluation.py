"""Evaluate synthetic structured histories with the existing Lane B engine."""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from io import StringIO

from boussla.checks import ChecksEngineV4
from boussla.contracts import Finding, FindingFamily, FindingStatus, ScoreResult, TransactionInputs
from boussla.scoring import METHOD, count_unresolved_transactions


def _percent(numerator: int, denominator: int) -> str | None:
    if not denominator:
        return None
    value = Decimal(numerator) * 100 / Decimal(denominator)
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def evaluate_screening_population(population: dict) -> dict:
    """Run each revision, then aggregate only its latest accepted state."""
    engine = ChecksEngineV4()
    company_scores = defaultdict(list)
    company_findings = defaultdict(list)
    company_coverage = defaultdict(lambda: [0, 0])
    company_contributors = defaultdict(Counter)
    finding_statuses = defaultdict(Counter)
    transactions = []
    for row in population["transactions"]:
        revisions = []
        for source in row["revisions"]:
            inputs = TransactionInputs.model_validate(source)
            findings = engine.evaluate_transaction(inputs)
            score = engine.score_transaction(findings, set(FindingFamily))
            revisions.append({
                "case_version": inputs.case_version,
                "score": score.model_dump(mode="json"),
                "findings": [finding.model_dump(mode="json") for finding in findings],
            })
        current = revisions[-1]
        company_id = row["company_id"]
        company_scores[company_id].append(current["score"])
        company_findings[company_id].extend(current["findings"])
        company_coverage[company_id][0] += len(current["score"]["evaluable_families"])
        company_coverage[company_id][1] += len(FindingFamily)
        for finding in current["findings"]:
            finding_statuses[finding["family"]][finding["status"]] += 1
            if finding["status"] == FindingStatus.UNRESOLVED.value and finding["evidence_refs"]:
                company_contributors[company_id][finding["family"]] += 1
        transactions.append({"transaction_id": row["transaction_id"],
                             "company_id": company_id, "revisions": revisions})

    companies = []
    distribution = Counter()
    total_evaluable_checks = 0
    total_applicable_checks = 0
    for company in population["companies"]:
        company_id = company["company_id"]
        scores = company_scores[company_id]
        indices = [score["review_index"] for score in scores if score["review_index"] is not None]
        index = engine.aggregate_company([ScoreResult.model_validate(score) for score in scores])
        assert index == (max(indices) if indices else None)
        distribution["null" if index is None else str(index)] += 1
        evaluable, applicable = company_coverage[company_id]
        total_evaluable_checks += evaluable
        total_applicable_checks += applicable
        current_findings = company_findings[company_id]
        unresolved_count = count_unresolved_transactions(
            Finding.model_validate(finding) for finding in current_findings)
        companies.append({
            "company_id": company_id, "display_name": company["display_name"],
            "review_index": index, "transaction_count": len(scores),
            "evaluable_transactions": len(indices), "null_transactions": len(scores) - len(indices),
            "unresolved_distinct_transactions": unresolved_count,
            "coverage_evaluable_checks": evaluable,
            "coverage_known_applicable_checks": applicable,
            "evidence_coverage_percent": _percent(evaluable, applicable),
            "coverage_complete": all(score["coverage_complete"] for score in scores),
            "contributing_families": dict(sorted(company_contributors[company_id].items())),
            "max_index_transaction_ids": [score["transaction_id"] for score in scores
                                          if index is not None and score["review_index"] == index],
            "mode": population["source_mode"], "not_fraud_probability": True,
        })
    return {
        "population_version": population["version"], "seed": population["seed"],
        "mode": population["source_mode"], "method": METHOD,
        "company_count": len(companies), "transaction_count": len(transactions),
        "null_company_count": distribution["null"],
        "evaluable_company_count": len(companies) - distribution["null"],
        "review_index_distribution": dict(sorted(distribution.items())),
        "coverage_evaluable_checks": total_evaluable_checks,
        "coverage_known_applicable_checks": total_applicable_checks,
        "evidence_coverage_percent": _percent(total_evaluable_checks, total_applicable_checks),
        "finding_status_counts": {family: dict(sorted(statuses.items()))
                                  for family, statuses in sorted(finding_statuses.items())},
        "companies": companies, "transactions": transactions,
    }


QUEUE_COLUMNS = (
    "company_id", "display_name", "review_index", "transaction_count",
    "evaluable_transactions", "null_transactions", "unresolved_distinct_transactions",
    "coverage_evaluable_checks", "coverage_known_applicable_checks",
    "evidence_coverage_percent", "coverage_complete", "contributing_families",
    "max_index_transaction_ids", "mode", "not_fraud_probability",
)


def render_company_queue_csv(evaluation: dict) -> str:
    """Stable, read-only queue export for an optional D-owned UI consumer."""
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=QUEUE_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for company in evaluation["companies"]:
        row = dict(company)
        row["review_index"] = "" if company["review_index"] is None else company["review_index"]
        row["contributing_families"] = ";".join(
            f"{family}:{count}" for family, count in company["contributing_families"].items())
        row["max_index_transaction_ids"] = ";".join(company["max_index_transaction_ids"])
        writer.writerow(row)
    return output.getvalue()
