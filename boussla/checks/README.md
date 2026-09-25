# Lane B pure checks

`ChecksEngineV4` implements the `ChecksEngine` protocol in `boussla.contracts`.
It accepts a scoped `TransactionInputs` supplied by lane A. The functions
read no database, clock, provider, global fixture, or hidden answer key.

```python
from boussla.checks import ChecksEngineV4
from boussla.contracts import FindingFamily

engine = ChecksEngineV4()
findings = engine.evaluate_transaction(inputs)
score = engine.score_transaction(findings, set(FindingFamily))
scenarios = engine.run_scenarios(inputs, {
    "quantity_margins": ["0", "0.10"],
    "candidate_reallocation": {"P1": "1000", "P2": "1000"},
})
```

For the included structured brick fixture, the three findings are
`EXPLAINED`, `EXPLAINED`, and `UNRESOLVED` with a 1,000-piece excess. The
review index is 40 with 100% known-applicable coverage. The margin scenarios
show 1,000 and 900 residual pieces. The candidate yields zero residual but
remains `CANDIDATE_UNACCEPTED`; it never changes `inputs`. After lane A accepts
a budget-valid 1,000/1,000 reallocation into a new case revision, evaluating
the revised inputs gives index 0. These are synthetic fixture outcomes, not
real-world detection metrics.

Current P0 limits: one confirmed buyer material line, source-lineage-backed
seller comparison, same-unit accepted delivery, and accepted scoped procurement
reference. An installment balance remains `INSUFFICIENT` because the shared
contract has no due schedule or complete-settlement coverage field. No
settlement points are emitted from that incomplete evidence. `aggregate_company`
returns only the maximum transaction index; the service owns snapshot scope,
history, and distinct event counts.

Verification: `python -m pytest -q tests/checks tests/backend` (58 passed on
the first integrated lane B slice, using pytest 9.1.1 and Pydantic 2.13.5).
