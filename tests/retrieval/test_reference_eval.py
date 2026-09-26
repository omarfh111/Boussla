from boussla.retrieval.corpus import load_public_references
from boussla.retrieval.lexical import LexicalReferenceRetriever
from scripts.evaluate_reference_retrieval import load_cases, run_evaluation


def test_fixed_synthetic_evaluation_is_bounded_and_references_manifest():
    cases = load_cases()
    assert len(cases) == 21
    assert sum("reason_code" in case for case in cases) >= 4
    assert sum(bool(case.get("compare_lexical")) for case in cases) >= 4
    assert all("PRIVATE" not in str(case) for case in cases)


def test_lexical_evaluation_reports_actual_hits_and_modes():
    rows, totals = run_evaluation(LexicalReferenceRetriever(load_public_references()), load_cases())
    assert totals["cases"] == 21
    assert 0 <= totals["top1"] <= totals["top3"] <= 21
    assert all(row["mode"] in {"TEMPLATE", "NOT_RUN"} for row in rows)
    assert all(len(row["returned_ids"]) <= 3 for row in rows)
