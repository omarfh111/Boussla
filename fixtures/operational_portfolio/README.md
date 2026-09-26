# Synthetic operational portfolio

Runtime artifact: `portfolio.json`. Regenerate with:

```powershell
python -m boussla.data.operational_portfolio
```

Fixed observation cutoff: 2026-01-10 UTC. Coverage: January–December 2025.
12 synthetic enterprises, 147 purchase transactions (12–15 per enterprise),
135 buyer/seller pairs and 12 buyer-only observations. Counterparties are scoped
fictional supplier identities, not additional registered demo enterprises.

Every invoice pair represents one economic transaction. Buyer/company uploads
and simulated seller records have distinct document IDs, origins and uploaders.
Agreement means independent synthetic observations agree; it does not validate
a declaration. Structured source records are simulated provenance, not real files
or authenticated records. No government documents or bank integration are used.

The financial snapshot counts each buyer invoice once, applies documented accepted
credit adjustments, and excludes reversed payments from observed settled outflows.
It covers the generated purchase ledger only: zero observed inflows is not a claim
of zero enterprise revenue. Outstanding payable is not an overdue debt conclusion.
The `synthetic_authorized_financial_snapshot` field is synthetic context, not proof.

## Lane A integration contract

Import from `boussla.data.operational_portfolio`:

- `seed_portfolio(path=None)` generates defaults; supplying `FIXTURE` loads the committed artifact.
- `list_enterprises(portfolio)` returns shared `Enterprise` models.
- `enterprise_facts(portfolio, company_id)` returns a validated, deep-copied bundle.
- `transaction_inputs(portfolio, company_id)` returns shared `TransactionInputs` models.
- `case_facts(portfolio, company_id)` returns typed fact lists keyed by store kind.
- `reset_portfolio(portfolio)` returns a fresh default portfolio.
- `add_synthetic_enterprise(portfolio, enterprise)` accepts a complete scoped bundle
  or an `Enterprise` identity (creating an empty enterprise with no claimed coverage).
- `delete_synthetic_enterprise(portfolio, company_id)` removes only that bundle.

All management operations return new data; they never mutate the input, database,
files, services or graph. Unknown IDs fail instead of selecting a default company.
Duplicate identities, scope mismatches and inconsistent financial snapshots fail.
These functions are not authorization endpoints. A owns caller authorization,
actor registration, persistence, case versions, reset/delete confirmations and API wiring.
`case_facts` includes `settlement_adjustment`; A must support that kind explicitly
when persisting the credit-note example. Keep source records and monthly coverage
alongside canonical facts for the history/context consumers.

The existing quantity check honestly returns INSUFFICIENT for warehouse scope and
for assets without project allocation. Partial settlement with unknown due terms
also remains INSUFFICIENT. The data does not force these cases into a resolved state.
No production check, score, service, workflow or UI was changed.

## Historical observations for A/C

`boussla.history_signals.analyze_history(inputs, company_id=..., as_of=..., coverage=...)`
returns immutable `HistorySignal` values. `inputs` are shared `TransactionInputs`;
`coverage` maps complete synthetic ledger months (`YYYY-MM`) to their source IDs.
Use the enterprise bundle's coverage records. Pass an explicit timezone-aware cutoff.
Only completed, covered months and source views available by that cutoff are used.
Unknown months are never converted into zero activity. Duplicate transactions and
mixed-company documents/payments/invoices are rejected. No clock, network or mutation.

The output includes code, period, metric, observed/baseline values, baseline periods,
source IDs, French neutral explanation, method version and `affects_review_index=False`.
Thresholds are descriptive demo conventions:

| Code | Definition |
|---|---|
| ACTIVITY_GAP | At least two consecutive covered months without available buyer-invoice activity |
| LATE_DOCUMENT_ACTIVITY | Buyer document available more than 45 days after issue; 45 is a descriptive threshold |
| VOLUME_SPIKE | Monthly transaction count at least 3× the previous three covered months' mean, mean at least 1 |
| VOLUME_DROP | Monthly count at most ⅓ of that mean |
| PAYMENT_PATTERN_CHANGE | Absolute change at least 0.4 in observed settlement/gross ratio versus the previous three months |
| COUNTERPARTY_CONCENTRATION_CHANGE | Absolute change at least 0.4 in largest supplier's transaction share between latest two covered quarters |
| REPEATED_INVOICE_CONFLICT | At least two distinct transactions with current counterparty conflicts in latest covered quarter |
| NO_SIGNIFICANT_CHANGE | No descriptive threshold met on sufficient covered history; no validation of declarations |
| INSUFFICIENT_HISTORY | No usable consecutive baseline/observations; never interpreted as clean |

Payment ratios attribute observed settlements to the transaction's economic month
as known at the explicit cutoff. They are not historical account balances, due-date
judgments or contemporaneous month-end snapshots. All monetary comparisons are TND.
Counterparty repetition delegates to existing `ChecksEngineV4`; no new score logic.
History codes are review/context candidates, not financial findings or probabilities.

The archetype checklist and expected compatibility values are exclusively under
`evaluation_only/`, which neither runtime module nor evaluator reads. The test suite
reads this oracle separately. `results/operational_portfolio/` contains computed
observations from current checks/history rules; it is not a runtime answer key.

```python
from datetime import datetime
from boussla.data.operational_portfolio import seed_portfolio, enterprise_facts, transaction_inputs
from boussla.history_signals import analyze_history

portfolio = seed_portfolio()
company_id = "SYN-OP-006"
bundle = enterprise_facts(portfolio, company_id)
signals = analyze_history(
    transaction_inputs(portfolio, company_id), company_id=company_id,
    as_of=datetime.fromisoformat(portfolio["as_of"]),
    coverage={row["period"]: row["source_id"] for row in bundle["coverage"]},
)
```
