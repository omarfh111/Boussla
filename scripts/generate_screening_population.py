"""Regenerate the committed structured screening population fixture."""

import json
from pathlib import Path

from boussla.data.screening_population import generate_screening_population


def main() -> None:
    output = (Path(__file__).resolve().parents[1] / "boussla" / "data" / "fixtures"
              / "screening_population.json")
    output.write_text(json.dumps(generate_screening_population(), separators=(",", ":")) + "\n",
                      encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
