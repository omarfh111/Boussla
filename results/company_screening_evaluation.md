# Synthetic company screening evaluation

This is a deterministic **synthetic structured-input** exercise of the existing
`ChecksEngineV4` and `CONTEXT_RULES_V4_1` scoring method. It is a review-priority
demonstration, **not a fraud prediction benchmark**. No hidden fraud labels,
LLM calls, PDF extraction, live provider data, or real taxpayer records are
used. Index `null` means no check was evaluable; index `0` only describes the
checks that were evaluable. The index is **priority for human review, not a
probability of fraud**.

## Population and outputs

- Fixed seed: `20260926`; generator version: `SYNTHETIC_SCREENING_V1`.
- 40 companies, 12 monthly purchase events per company in 2025, 480 distinct
  transactions. Invoice, settlement, delivery and allocation views are linked
  to those events. Five transactions also retain an earlier review revision.
- [Structured population](../boussla/data/fixtures/screening_population.json),
  [transaction and company results](company_screening_results.json), and
  [company queue CSV](company_screening_queue.csv) are generated artifacts.
  The JSON result includes every finding, reason, evidence reference and score
  per revision. The CSV has one row per company.
- Monthly history separates invoiced purchases from observed settlement.
  Declared totals are `null`/`NOT_SUPPLIED`, since no declaration source exists.
  Generated document metadata describes synthetic JSON records, not PDFs.

Regenerate with `python -m scripts.generate_screening_population` and then
`python -m scripts.evaluate_screening_population` from the repository root.

## Recorded current-state results

| Measure | Result |
|---|---:|
| Companies with evaluable index | 35 |
| Companies with null index | 5 |
| Review index 0 | 20 companies |
| Review index 35 | 5 companies |
| Review index 40 | 10 companies |
| Evaluable / known-applicable family checks | 1,195 / 1,440 (82.99%) |
| Companies with complete family coverage | 25 |

Current finding families are counted per distinct transaction, not per upload
or retained revision:

| Family | Explained | Insufficient | Unresolved |
|---|---:|---:|---:|
| Counterparty | 350 | 120 | 10 |
| Settlement | 415 | 65 | 0 |
| Quantity | 410 | 60 | 10 |

The 10 supported counterparty conflicts and 10 supported quantity discrepancies
contribute under the unchanged 35/25/40 baseline. Settlement produces no
unresolved contribution because the shared input contract has no due schedule
or completeness signal; a residual abstains. A company with two independent
unresolved transactions has an index of 40 (the maximum transaction index)
and an unresolved transaction count of 2. Those are separate queue signals.

## Same amount, different review priority

`SYN-C001-TX-01`, `SYN-C002-TX-01`, and `SYN-C003-TX-01` each have a buyer-view
gross invoice of **1,190,000 millimes**. C001's independent invoice, payment,
and allocation comparisons are explained, so its transaction index is 0 with
full coverage. C002 assigns 100 units to a work package with a 50-unit accepted
procurement reference, producing a supported quantity contribution of 40.
C003 has an independently sourced conflicting seller-view amount, producing a
counterparty contribution of 35. The invoiced amount alone does not determine
review priority, and neither difference establishes misconduct.

Other useful situations are visible without hidden labels: C004 has no
confirmed/evaluable observations and a null index; C005's half settlement is
insufficient because the due schedule is unknown; C006's accepted reallocation
changes its first transaction from index 40 in version 1 to 0 in version 2;
C007 lacks independent counterpart coverage but has a partial index of 0 from
the other families; C008 has two distinct unresolved transactions while its
company index remains the maximum transaction index of 40. These patterns
repeat across the 40-company population with varied synthetic amounts.

## Consumption and limits

The CSV is a **read-only evaluation queue contract**: `company_id`,
`review_index` (blank for null), evaluable/null transaction counts, distinct
unresolved transaction count, evidence-coverage numerator/denominator/percent,
coverage-complete flag, contributing families, and maximum-index transaction
IDs. The JSON supplies the linked per-transaction findings and revisions. D
could load these artifacts into a separate clearly marked synthetic screening
view and link rows by `company_id` and `transaction_id`; A would need to decide
whether and how any such data enters the authoritative service/store. This
evaluation does not write either lane's files or create a live multi-company
queue.

No extraction accuracy, fraud detection rate, recall, calibration, or
real-world performance is inferred. The populations are deliberately designed
review situations, not a representative sample. Counterpart independence is
simulated provenance only. The current quantity path covers one material line
and accepted same-unit procurement references. A service/UI integration and
PDF/provider path remain `NOT_RUN` for this population.

Validation before the `b4fc655` main sync: **234 passed** across
`tests/checks`, `tests/backend`, `tests/adapters`, `tests/documents`,
`tests/integration`, `tests/retrieval`, and
`docs/build_lock/reference/test_core.py`. The full UI suite was not executed in
this isolated runner because Streamlit is not installed there; the earlier
full-suite attempt stopped at collection on two Streamlit imports. No UI file
was changed for this evaluation.
