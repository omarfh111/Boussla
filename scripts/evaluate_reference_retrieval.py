"""Fixed synthetic retrieval metrics; these are not legal-accuracy metrics."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from boussla.contracts import Audience, FindingFamily, Mode
from boussla.retrieval.corpus import load_public_references, public_reference_retriever
from boussla.retrieval.lexical import LexicalReferenceRetriever
from boussla.retrieval.queries import query_for_reason


EVAL_PATH = Path(__file__).resolve().parents[1] / "boussla" / "retrieval" / "reference_eval.json"
AS_OF = date(2026, 9, 26)


def load_cases(path: Path = EVAL_PATH) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    known = {record.rule_id for record in load_public_references()}
    if not isinstance(cases, list) or not 15 <= len(cases) <= 25:
        raise ValueError("expected 15–25 fixed synthetic retrieval cases")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or not {"id", "acceptable_ids"} <= case.keys():
            raise ValueError("malformed retrieval evaluation case")
        if case["id"] in ids or not set(case["acceptable_ids"]) <= known or not case["acceptable_ids"]:
            raise ValueError("duplicate case or unknown expected reference")
        ids.add(case["id"])
        query = (query_for_reason(FindingFamily.COUNTERPARTY, case["reason_code"])
                 if "reason_code" in case else case.get("query"))
        if not isinstance(query, str) or not 1 <= len(query) <= 160:
            raise ValueError("query must be bounded and mapped")
    return cases


def run_evaluation(retriever, cases: list[dict]) -> tuple[list[dict], dict]:
    rows = []
    for case in cases:
        query = (query_for_reason(FindingFamily.COUNTERPARTY, case["reason_code"])
                 if "reason_code" in case else case["query"])
        result = retriever.search(query, as_of=AS_OF, jurisdiction="TN", audience=Audience.OFFICER, limit=3)
        ids = [passage.rule_id for passage in result]
        expected = set(case["acceptable_ids"])
        rows.append({"id": case["id"], "top1": bool(ids and ids[0] in expected),
                     "top3": bool(expected.intersection(ids[:3])), "returned_ids": ids,
                     "mode": result[0].mode.value if result else Mode.NOT_RUN.value})
    return rows, {"cases": len(rows), "top1": sum(row["top1"] for row in rows),
                  "top3": sum(row["top3"] for row in rows)}


def main() -> None:
    cases = load_cases()
    retriever = public_reference_retriever()
    if retriever.backend_mode != "QDRANT":
        raise SystemExit(f"Qdrant evaluation unavailable: {retriever.backend_mode}")
    rows, totals = run_evaluation(retriever, cases)
    if retriever.backend_mode != "QDRANT" or any(row["mode"] != Mode.LIVE.value for row in rows):
        raise SystemExit("Cloud query failed during evaluation")
    print("backend", retriever.backend_mode, "cases", totals["cases"],
          "top1", totals["top1"], "top3", totals["top3"])
    for row in rows:
        print(row["id"], "top1", int(row["top1"]), "top3", int(row["top3"]),
              "ids", ",".join(row["returned_ids"]), "mode", row["mode"])
    lexical = LexicalReferenceRetriever(load_public_references())
    for case in (case for case in cases if case.get("compare_lexical")):
        semantic, semantic_totals = run_evaluation(retriever, [case])
        fallback, fallback_totals = run_evaluation(lexical, [case])
        print("compare", case["id"], "qdrant_top3", int(bool(semantic_totals["top3"])),
              "lexical_top3", int(bool(fallback_totals["top3"])),
              "qdrant_ids", ",".join(semantic[0]["returned_ids"]),
              "lexical_ids", ",".join(fallback[0]["returned_ids"]))


if __name__ == "__main__":
    main()
