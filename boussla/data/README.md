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
