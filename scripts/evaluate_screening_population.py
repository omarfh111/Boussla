"""Write reproducible machine-readable screening evaluation outputs."""

import json
from pathlib import Path

from boussla.data.screening_evaluation import evaluate_screening_population, render_company_queue_csv


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    population = json.loads((root / "boussla" / "data" / "fixtures"
                             / "screening_population.json").read_text(encoding="utf-8"))
    evaluation = evaluate_screening_population(population)
    result_dir = root / "results"
    (result_dir / "company_screening_results.json").write_text(
        json.dumps(evaluation, separators=(",", ":")) + "\n", encoding="utf-8")
    (result_dir / "company_screening_queue.csv").write_text(
        render_company_queue_csv(evaluation), encoding="utf-8")
    print(f"Evaluated {evaluation['company_count']} companies and "
          f"{evaluation['transaction_count']} transactions")


if __name__ == "__main__":
    main()
