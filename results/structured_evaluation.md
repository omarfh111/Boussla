# Lane B structured-input evaluation — 2026-09-25

Mode: **synthetic structured inputs only**. These tests bypass PDF extraction,
Jev, retrieval, the real service, and the UI. They use the supplied brick fixture
and controlled field variations. They are regression cases, not independent
fraud labels or a population accuracy estimate.

## Recorded result

`tests/checks/test_structured_evaluation.py`: **13/13** cases produced the
expected three finding statuses and review index. The full local check was
**103 passed, 0 failed** across lane B checks, lane A's backend tests, and the
pack reference suite.

| Structured case | Counterparty | Settlement | Quantity | Index |
|---|---|---|---|---:|
| Brick allocation | explained | explained | unresolved: 1,000 pieces | 40 |
| Independent counterpart amount conflict | unresolved: 1,190,000 millimes | insufficient | unresolved | 75 |
| Part payment | explained | insufficient; schedule unknown | unresolved | 40 |
| Same-origin copy | insufficient; independence unknown | explained | unresolved | 40 |
| Missing supplier view | insufficient | explained | unresolved | 40 |
| Accepted valid reallocation | explained | explained | explained | 0 |
| User-estimate reference | explained | explained | insufficient | 0 partial |
| Wrong-company seller view | insufficient | explained | unresolved | 40 |
| Over-budget double allocation | explained | explained | insufficient; invalid ledger | 0 partial |
| Missing delivery | explained | explained | insufficient | 0 partial |
| Independent invoice line conflict | unresolved | explained | unresolved | 75 |
| Incompatible quantity unit | explained | explained | insufficient | 0 partial |
| Unconfirmed buyer fields | insufficient | insufficient | insufficient | null |

The baseline scenario returns 1,000 residual pieces; a fictional +10% margin
returns 900. A proposed 1,000/1,000 reallocation has zero hypothetical
residual but cannot change accepted facts. Re-evaluation reaches index 0 only
after the accepted allocations are supplied in a new case version.

## Reproduction

On this Windows host, the environment command used was:

```powershell
$env:UV_CACHE_DIR='D:\hack_finance\.uv-cache'
$env:UV_PYTHON_INSTALL_DIR='D:\hack_finance\.uv-python'
uv run --system-certs --no-project --offline --python 'C:\Users\moham\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' --with pytest==9.1.1 --with pydantic==2.13.5 python -m pytest -o addopts='' -q -p no:cacheprovider tests/checks tests/backend docs/build_lock/reference/test_core.py
```

The tests completed with `103 passed in 0.23s`. The test environment includes
only pytest and Pydantic because these pure checks do not require the full
application dependency set.

## Limits and integration requests

- One supplied economic event was varied 13 ways; no claim about unseen
  companies, French PDF field extraction, or real tax outcomes follows.
- Part-payment residuals stay `INSUFFICIENT` because `TransactionInputs` lacks
  a due schedule, explicit settlement-completeness signal, and accepted net
  payable field. Lane A must decide and add those semantics before settlement
  discrepancies can safely earn points.
- Allocation acceptance and historical as-of scoping are supplied by lane A.
  These pure functions do not accept evidence or write case revisions.
- Lateness and clarification status are outside the pure financial checks.
  A late but valid response still needs service-level workflow testing.
- The current quantity path supports one confirmed material line, one unit,
  accepted delivery, and an approved procurement allocation. Other cases
  abstain rather than infer conversions or a stock transfer.
