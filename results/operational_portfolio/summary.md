# Synthetic operational portfolio — integration evidence

Base main: `b33ae94f37e09c7cf5aa76054d114176a843249a`.

12 enterprises; 147 transactions; 282 invoice observations; 135 independent synthetic pairs; 12 months.
Current checks are reused unchanged. History observations do not contribute to the review index.

| Enterprise | Transactions | Pairs | Current review index | Observed history codes |
|---|---:|---:|---:|---|
| SYN-OP-001 | 12 | 12 | 0 | NO_SIGNIFICANT_CHANGE |
| SYN-OP-002 | 12 | 12 | 35 | REPEATED_INVOICE_CONFLICT |
| SYN-OP-003 | 12 | 12 | 35 | NO_SIGNIFICANT_CHANGE |
| SYN-OP-004 | 12 | 0 | 0 | NO_SIGNIFICANT_CHANGE |
| SYN-OP-005 | 12 | 12 | 0 | ACTIVITY_GAP, LATE_DOCUMENT_ACTIVITY, VOLUME_DROP |
| SYN-OP-006 | 15 | 15 | 0 | VOLUME_SPIKE |
| SYN-OP-007 | 12 | 12 | 0 | VOLUME_DROP |
| SYN-OP-008 | 12 | 12 | 0 | PAYMENT_PATTERN_CHANGE |
| SYN-OP-009 | 12 | 12 | 32 | NO_SIGNIFICANT_CHANGE |
| SYN-OP-010 | 12 | 12 | 0 | NO_SIGNIFICANT_CHANGE |
| SYN-OP-011 | 12 | 12 | 0 | PAYMENT_PATTERN_CHANGE |
| SYN-OP-012 | 12 | 12 | 67 | COUNTERPARTY_CONCENTRATION_CHANGE, PAYMENT_PATTERN_CHANGE, REPEATED_INVOICE_CONFLICT |

## Integration boundary

A must authorize and persist portfolio management, register demo actors and wire API endpoints.
C can consume `HistorySignal` objects with source IDs, cutoff, baseline periods and neutral explanations.
D can consume A's future authorized endpoints. This branch contains no React/API/service changes.
Asset companies have no projects. Stock and missing-project quantity scope stay INSUFFICIENT under current checks.
A zero history-change signal does not mean an invoice is consistent, nor does a zero review index mean complete coverage.
A partial/reversed payment is not presumed overdue; due schedules are not supplied.
Financial snapshots are synthetic purchase-ledger context, not bank records or proof.

Runtime: `fixtures/operational_portfolio/portfolio.json`; evaluation checklist: `evaluation_only/archetypes.json`.
Regenerate: `python -m boussla.data.operational_portfolio` then `python -m boussla.data.operational_portfolio_evaluation`.
