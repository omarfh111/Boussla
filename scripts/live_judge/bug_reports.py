"""Produce reproducible defect handoffs from sanitized evaluator observations."""
import json
from pathlib import Path
from scripts.live_judge.pack import ROOT

ISSUES = [
    ("LJG-001", "CRITICAL", "JUDGE-008", "A", "Evidence acceptance without a supporting document",
     "Create the quantity-gap case. Publish clarification. Submit allocation P1=1000, P2=1000 with document_ids=[]. As the assigned officer, accept the proposal.",
     "Reject evidence acceptance; keep review_index=40.",
     "Acceptance succeeds and changes review_index from 40 to 0.",
     "_apply_proposal accepts an optional source_document_id without a supporting-document requirement."),
    ("LJG-002", "HIGH", "JUDGE-028", "A", "Wrong allocation unit/currency silently discarded",
     "Use tamper variants wrong_unit and wrong_currency: allocation unit='tonne' or currency='EUR', P1=1000, P2=1000. Submit and accept the resulting proposal.",
     "Reject unsupported or inconsistent allocation fields before canonical mutation.",
     "Both payloads are accepted; the index changes 40 to 0 using the original canonical unit/currency. This is silent field discard, not a proved currency conversion bug.",
     "_build_proposal selects known dictionary keys and ignores supplied unit/currency."),
    ("LJG-003", "MEDIUM", "JUDGE-028", "A", "Nonfinite/extreme allocation amounts raise untyped exceptions",
     "Use tamper variants infinity and huge_decimal: allocation splits={'P1':'Infinity'} or {'P1':'1e999999999'}.",
     "Typed INVALID_INPUT rejection; unchanged authoritative findings/index.",
     "ValidationError and decimal.Overflow escape the typed service error contract. Canonical score remains unchanged.",
     "Decimal parsing and AllocationChange validation do not consistently translate numeric exceptions."),
    ("LJG-004", "MEDIUM", "JUDGE-037", "A", "Unexpected context properties accepted",
     "submit_context with purpose_category='CONSTRUCTION_PROJECT', purpose_text='synthetic', review_index=0 and arbitrary_property='not-in-contract'.",
     "Typed rejection for unexpected JSON fields, as required by the judge contract.",
     "Submission commits one context revision and silently drops extra properties. The supplied review_index does not override the authoritative score.",
     "Dictionary input is filtered to known fields instead of strictly validated."),
    ("LJG-005", "MEDIUM", "JUDGE-054", "C", "Definitive applicability wording bypasses RAG guard",
     "Return a schema-valid model claim with a retrieved rule ID and either 'This law definitely applies to this company.' or 'Cette règle s’applique au dossier.'.",
     "Reject definitive applicability; retain candidate passages with no note.",
     "Both claims are accepted as grounded notes. Findings/index remain unchanged and notes remain officer-only.",
     "The forbidden-language regex covers a limited French form and misses English and Unicode apostrophes."),
]


def main():
    report = json.loads((ROOT / "results/live_judge/report.json").read_text(encoding="utf-8"))
    folder = ROOT / "results/live_judge/bugs"
    folder.mkdir(parents=True, exist_ok=True)
    for ident, severity, sid, owner, title, steps, expected, actual, cause in ISSUES:
        row = next(r for r in report["scenarios"] if r["scenario_id"] == sid)
        text = f"""# {ident}: {title}

Status: RED_UNRESOLVED — NOT READY TO MERGE

- ID: {ident}
- Severity: {severity}
- Scenario: {sid}
- Component: {'service input/evidence boundary' if owner == 'A' else 'grounded RAG validation'}
- Owner suggestion: {owner}
- Tested production base: {report['base_main_sha']}

## Preconditions and exact input

Use the checked-in synthetic scenario and observed facts at
`fixtures/live_judge/scenarios/{sid}.json` and its `observed_file`.
The harness creates a disposable real SQLite/service instance. Providers are disabled,
except deliberately injected model output for the RAG regression.

{steps}

## Expected

{expected}

## Actual

{actual}

## Reproduction

```powershell
python -m scripts.live_judge.run --mode offline --scenario {sid} --report results/live_judge/reproduction.json
python -m pytest -o addopts='' tests/live_judge/test_regressions.py -k {sid}
```

Regression path: `tests/live_judge/test_regressions.py`.
Exact driver: `scripts/live_judge/checks.py` (or `provider_checks.py` for RAG).

## Authoritative state before/after and safe logs

The following are synthetic evaluator observations. No provider messages or credentials.
For JUDGE-028, `tamper_cases` contains the independent before/after state for each input;
the parent case stays unchanged.

```json
{json.dumps({'failures': row['failures'], 'state': row['details']}, indent=2, ensure_ascii=False)}
```

## Suggested likely cause — do not implement a fix in this lane

{cause}
"""
        (folder / f"{ident}.md").write_text(text, encoding="utf-8")
    print(f"Wrote {len(ISSUES)} unresolved issue reports")


if __name__ == "__main__":
    main()
