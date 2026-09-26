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
