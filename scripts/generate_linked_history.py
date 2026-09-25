"""Write the fixed small synthetic linked history used for development."""

import json
from pathlib import Path

from boussla.data import generate_linked_history


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "boussla" / "data" / "fixtures" / "linked_history.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(generate_linked_history(), indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
