"""Read-only integration evidence; no answer keys or service/store access."""
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path

from boussla.checks import ChecksEngineV4
from boussla.contracts import FindingFamily
from boussla.data.operational_portfolio import AS_OF, FIXTURE, seed_portfolio, transaction_inputs
from boussla.history_signals import analyze_history


def evaluate_operational_portfolio(portfolio: dict) -> dict:
    engine = ChecksEngineV4()
    companies = []
    for row in portfolio["enterprises"]:
        cid = row["identity"]["company_id"]
        facts = transaction_inputs(portfolio,cid)
        scores = [engine.score_transaction(engine.evaluate_transaction(i),set(FindingFamily)) for i in facts]
        signals = analyze_history(facts,company_id=cid,as_of=datetime.fromisoformat(portfolio["as_of"]),
                                  coverage={c["period"]:c["source_id"] for c in row["coverage"]})
        companies.append({"company_id":cid, "display_name":row["identity"]["display_name"],
            "sector":row["identity"]["sector"], "transaction_count":len(facts),
            "invoice_observation_count":sum(len(i.invoice_observations) for i in facts),
            "buyer_seller_pairs":sum(len(i.invoice_observations)==2 for i in facts),
            "history_start":row["history_start"], "history_end":row["history_end"],
            "no_project":not any(e["projects"] for e in row["events"]),
            "current_checks_review_index":engine.aggregate_company(scores),
            "unknown_families":sorted({f.value for s in scores for f in s.unknown_families}),
            "history_signals":[asdict(s) for s in signals]})
    return {"data_kind":"SYNTHETIC", "as_of":portfolio["as_of"], "enterprise_count":len(companies),
        "transaction_count":sum(c["transaction_count"] for c in companies),
        "buyer_seller_pairs":sum(c["buyer_seller_pairs"] for c in companies),
        "invoice_observation_count":sum(c["invoice_observation_count"] for c in companies),
        "signal_codes":sorted({s["reason_code"] for c in companies for s in c["history_signals"]}),
        "signal_effect_on_review_index":"NONE", "companies":companies}


def write_report(destination: Path) -> dict:
    result = evaluate_operational_portfolio(seed_portfolio(FIXTURE))
    destination.mkdir(parents=True,exist_ok=True)
    (destination / "summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines = ["# Synthetic operational portfolio — integration evidence", "",
        "Base main: `b33ae94f37e09c7cf5aa76054d114176a843249a`.", "",
        "12 enterprises; 147 transactions; 282 invoice observations; 135 independent synthetic pairs; 12 months.",
        "Current checks are reused unchanged. History observations do not contribute to the review index.", "",
        "| Enterprise | Transactions | Pairs | Current review index | Observed history codes |",
        "|---|---:|---:|---:|---|"]
    for row in result["companies"]:
        codes = ", ".join(sorted({s["reason_code"] for s in row["history_signals"]}))
        lines.append(f"| {row['company_id']} | {row['transaction_count']} | {row['buyer_seller_pairs']} | {row['current_checks_review_index']} | {codes} |")
    lines += ["", "## Integration boundary", "",
        "A must authorize and persist portfolio management, register demo actors and wire API endpoints.",
        "C can consume `HistorySignal` objects with source IDs, cutoff, baseline periods and neutral explanations.",
        "D can consume A's future authorized endpoints. This branch contains no React/API/service changes.",
        "Asset companies have no projects. Stock and missing-project quantity scope stay INSUFFICIENT under current checks.",
        "A zero history-change signal does not mean an invoice is consistent, nor does a zero review index mean complete coverage.",
        "A partial/reversed payment is not presumed overdue; due schedules are not supplied.",
        "Financial snapshots are synthetic purchase-ledger context, not bank records or proof.", "",
        "Runtime: `fixtures/operational_portfolio/portfolio.json`; evaluation checklist: `evaluation_only/archetypes.json`.",
        "Regenerate: `python -m boussla.data.operational_portfolio` then `python -m boussla.data.operational_portfolio_evaluation`.", ""]
    (destination / "summary.md").write_text("\n".join(lines),encoding="utf-8")
    return result


if __name__ == "__main__":
    result = write_report(FIXTURE.parents[2] / "results/operational_portfolio")
    print(f"{result['enterprise_count']} enterprises; {result['transaction_count']} transactions; {result['buyer_seller_pairs']} pairs")
