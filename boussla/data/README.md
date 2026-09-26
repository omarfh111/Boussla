# Linked synthetic history

`history.py` builds one fictional event ledger and derives buyer and seller
invoice views, explicitly allocated settlement views, and monthly synthetic
declaration totals from it. `views_as_of` filters each source by its own
availability date, so later records do not appear in earlier snapshots.

The committed fixture contains 24 events over 12 months: 48 invoice views,
28 payment installments, and 24 company-period totals. Four transactions
have two installments. All values are fictional TND millimes. This is a small
development history, not a live feed, tax return, or representative sample.

Regenerate it from the repository root with:

```text
python -m scripts.generate_linked_history
```

The generator is deterministic. The service may use the source views as demo
data; it must not interpret the underlying event ledger as externally observed
evidence. There are no hidden fraud labels in this fixture.

## Structured company screening population

`screening_population.py` generates 40 synthetic companies with one linked
purchase event per month in 2025 (480 distinct transactions). Every transaction
has a typed `TransactionInputs` revision with its buyer invoice view and, when
available, a simulated independent seller view, settlement allocation, source
mapping, delivery, and accepted procurement allocation. Five transactions
retain both the initial and accepted-reallocation revisions. `monthly_history`
derives invoiced purchases and observed settlement from those same events;
declared totals are `null` because no declaration source was supplied.

The committed `fixtures/screening_population.json` is fully synthetic structured
data. Its document rows describe generated JSON source views, not materialized
PDFs or authenticated supplier records. The `sha256` field hashes the synthetic
view payload. The fixture has no fraud labels or expected score fields. It is
for the evaluation script and tests; the live service does not load it.

Regenerate from the repository root with
`python -m scripts.generate_screening_population`. The default fixed seed is
`20260926`; the generator accepts 30–50 companies for test variations.
