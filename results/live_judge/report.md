# LIVE JUDGE GAUNTLET — ROUND 1

Tested commit: `68cc9c45e576ad0664a0032df8945689a9e5d5d6`
Base main: `320e36bdc1733e0e7097fff37406cd7ec040a4ee`
Recorded: 2026-09-26T03:09:31.157682+00:00

Synthetic only. Production code is unchanged. Fault injection is labelled offline; it is not a live-provider success.

## Outcomes

| Outcome | Count |
|---|---:|
| PASS | 32 |
| SAFE_REJECTION | 4 |
| SAFE_FALLBACK | 3 |
| MANUAL_REQUIRED | 4 |
| BUG | 4 |
| NOT_RUN | 7 |

## Scenario matrix

| Scenario | Situation | Mode | Outcome |
|---|---|---|---|
| JUDGE-001 | CLEAN MATCH | offline | PASS |
| JUDGE-002 | COUNTERPARTY AMOUNT CONFLICT | offline | PASS |
| JUDGE-003 | MISSING INVOICE FIELD | offline | PASS |
| JUDGE-004 | PARTIAL PAYMENT | offline | PASS |
| JUDGE-005 | UNKNOWN PAYMENT TERMS | offline | PASS |
| JUDGE-006 | QUANTITY ALLOCATION GAP | offline | PASS |
| JUDGE-007 | VALID SECOND-PROJECT EVIDENCE | offline | PASS |
| JUDGE-008 | DECLARATION ONLY | offline | BUG |
| JUDGE-009 | SAME SOURCE | offline | PASS |
| JUDGE-010 | CONFLICTING SELLER VIEW | offline | PASS |
| JUDGE-011 | CREDIT NOTE | offline | MANUAL_REQUIRED |
| JUDGE-012 | DELIVERY RECORD | offline | MANUAL_REQUIRED |
| JUDGE-013 | DOCUMENT INJECTION | offline | MANUAL_REQUIRED |
| JUDGE-014 | MALFORMED PDF | offline | SAFE_REJECTION |
| JUDGE-015 | BLANK PDF | offline | MANUAL_REQUIRED |
| JUDGE-016 | LARGE PDF | offline | SAFE_REJECTION |
| JUDGE-017 | STALE VERSION | offline | SAFE_REJECTION |
| JUDGE-018 | DOUBLE SUBMIT | offline | PASS |
| JUDGE-019 | PROVIDER FAILURE CHAOS | offline | SAFE_FALLBACK |
| JUDGE-020 | ROLE TAMPERING | offline | SAFE_REJECTION |
| JUDGE-021 | REVERSED PAYMENT | offline | PASS |
| JUDGE-022 | UNKNOWN SETTLEMENT | offline | PASS |
| JUDGE-023 | STOCK | offline | PASS |
| JUDGE-024 | RETURNS | offline | PASS |
| JUDGE-025 | SAME NUMBER DIFFERENT SELLER | offline | PASS |
| JUDGE-026 | MULTIPLE INVOICE VERSIONS | offline | PASS |
| JUDGE-027 | UNKNOWN ACCOUNT MAPPING | offline | PASS |
| JUDGE-028 | INPUT TAMPERING | offline | BUG |
| JUDGE-029 | WEIRD PURPOSE | offline | PASS |
| JUDGE-030 | DOCUMENT MATRIX | offline | PASS |
| JUDGE-031 | ANALYSIS RESTART | offline | PASS |
| JUDGE-032 | DECISION RESTART | offline | PASS |
| JUDGE-033 | TWO CLIENTS | offline | PASS |
| JUDGE-034 | RAG PRIVACY AND CITATIONS | offline | PASS |
| JUDGE-035 | MODEL OUTPUT TAMPERING | offline | PASS |
| JUDGE-036 | TRACE PRIVACY AND OUTAGE | offline | SAFE_FALLBACK |
| JUDGE-037 | UNEXPECTED JSON PROPERTIES | offline | BUG |
| JUDGE-038 | UPLOAD RETRY AND DUPLICATES | offline | PASS |
| JUDGE-039 | REVISION IMMUTABILITY | offline | PASS |
| JUDGE-040 | SHORT VS 18 MONTHS | offline | NOT_RUN |
| JUDGE-041 | LONGER COMPLETE | offline | NOT_RUN |
| JUDGE-042 | LONGER MISSING STAGE | offline | NOT_RUN |
| JUDGE-043 | MISSING DATES | offline | NOT_RUN |
| JUDGE-044 | END BEFORE START | offline | NOT_RUN |
| JUDGE-045 | LLM DISAGREES WITH DATES | offline | NOT_RUN |
| JUDGE-046 | REACT API BROWSER | offline | NOT_RUN |
| JUDGE-047 | LIVE JEV | live | PASS |
| JUDGE-048 | LIVE EXTRACTION | live | SAFE_FALLBACK |
| JUDGE-049 | LIVE PLANNER | live | PASS |
| JUDGE-050 | LIVE QDRANT | live | PASS |
| JUDGE-051 | LIVE GROUNDED RAG | live | PASS |
| JUDGE-052 | LIVE LANGSMITH | live | PASS |
| JUDGE-053 | LIVE VERSUS FALLBACK | live | PASS |
| JUDGE-054 | RAG APPLICABILITY BYPASS | offline | BUG |

## Defects

- **CRITICAL / A / JUDGE-008**: documentless_acceptance_rejected
- **CRITICAL / A / JUDGE-008**: unsupported_claim_cannot_clear_index
- **MEDIUM / A / JUDGE-028**: tamper_infinity_typed_rejection
- **MEDIUM / A / JUDGE-028**: tamper_huge_decimal_typed_rejection
- **MEDIUM / A / JUDGE-028**: tamper_wrong_unit_typed_rejection
- **HIGH / A / JUDGE-028**: tamper_wrong_unit_no_score_change
- **MEDIUM / A / JUDGE-028**: tamper_wrong_currency_typed_rejection
- **HIGH / A / JUDGE-028**: tamper_wrong_currency_no_score_change
- **MEDIUM / A / JUDGE-037**: unexpected_properties_rejected
- **MEDIUM / C / JUDGE-054**: rag_rejects_english
- **MEDIUM / C / JUDGE-054**: rag_rejects_curly_apostrophe

## Interpretation

Each scenario has exactly one outcome. A scenario with any violated invariant is BUG. NOT_RUN is never a pass.
See report.json for before/after states, typed errors, privacy booleans and measured provider latencies.
Context and React scenarios remain PENDING until the captain authorizes Round 2 on their merged main.
Live model wording can vary. This tests invariants and synthetic routing, not legal accuracy or real-world performance.
Live configurations use the explicit private dotenv path; values, raw headers and provider error messages are never reported.
Runtime databases use disposable per-scenario OS temporary directories. No developer demo database was touched.

ROUND 2 REQUIRED: YES. No production fixes or main merge were performed.

## Round 1 handoff

Branch: `test/live-judge-gauntlet`. Tested harness SHA: `68cc9c4`.
Base main SHA: `320e36bdc1733e0e7097fff37406cd7ec040a4ee`.
The final artifact commit follows this tested harness commit.

Scenario pack: 54 scenarios, 30 generated files (28 valid PDFs, two intentionally
invalid PDF-labelled files). Types: invoices, payment records, delivery records,
credit notes, allocation references/responses, and ambiguous/injection variants.

Tests: **333 passed** in the green full relevant suite. **4 failed** in the separate
unresolved-regression suite. These four scenarios represent five issue reports.
No xfail or skip disguises a production defect.

### Critical bugs

- LJG-001 / A: documentless declaration can be accepted by the officer; priority 40 to 0.

### High bugs

- LJG-002 / A: supplied wrong unit/currency is silently discarded and acceptance clears priority.

### Medium bugs

- LJG-003 / A: Infinity and extreme decimal input escape as untyped exceptions.
- LJG-004 / A: extra context JSON properties are silently accepted.
- LJG-005 / C: English and curly-apostrophe definitive applicability claims pass the RAG guard.

Low bugs: none observed. Exact reproductions and before/after observations are in `bugs/`.

### Authoritative invariants

LIVE/fallback normalized findings, review index, evidence coverage, accepted-evidence
counts and revision counts match for JUDGE-001/002/006. Quantity acceptance is 40 to 0
in both modes. AI proposals do not automatically accept evidence. Officer acceptance
is defective for declaration-only input (LJG-001). Existing revision immutability,
service role isolation, same-key replay, conflicting-key rejection, stale writes and
two-client concurrency passed. Equality is scoped to these synthetic cases and the
normalized fields recorded in JSON, not arbitrary provider prose or random IDs.

### Privacy and resilience

OpenAI extraction/RAG/planner HTTP audits found no answer-key markers or disallowed
destinations. RAG/planner private-token checks passed. Extraction legitimately receives
the generated synthetic document text. Qdrant queries match bounded reason strings,
then send 384-dimensional vectors; cloud payloads match the reviewed public corpus.
The model sample vector was verified against the expected local embedding model.
LangSmith scans inspect inputs, outputs, metadata, tags and errors for selected
synthetic private identifiers, answer text and credentials; inputs/outputs were hidden.
This is bounded test evidence, not an exhaustive proof against every possible leak.

Injected OpenAI/Jev/Qdrant/LangSmith outages safely degraded. These are simulated
provider faults through real adapters/workflow, not deliberate outages of cloud accounts.
Score/findings stayed unchanged. RAG retained passages without a generated note.

### Prompt injection and concurrency

Document injection preserved schema/span boundaries and did not change authoritative
state in the live/fallback comparison. Fabricated IDs and invented citation IDs were
rejected. Retrieved instructions did not authorize an invented citation. Definitive
applicability-language validation has LJG-005 and needs repair.
Two SQLite clients, double submit, and separate-process analysis/decision restart-resume
passed; exactly one canonical acceptance revision was produced.

### Pending integration

Six context consistency cases are PENDING. The React/API/browser scenario is PENDING.
No browser, HTTP-header authorization, UI reload, or final integrated context behavior
is claimed from service tests. A/C fix the reported defects centrally. D can consume
`fixtures/live_judge/manifest.json`, scenario JSON, generated documents, and the isolated
service factory in `scripts/live_judge/support.py` for final HTTP/browser automation.
No A/D production files were changed.

### Provider observations and latency

These are observed synthetic-demo timings, not SLA guarantees.

| Provider/component | Observation | Measured latency ms |
|---|---|---:|
| Jev routing | PASS | 251.00–417.66 |
| OpenAI extraction | SAFE_FALLBACK | 2005.16–2982.11 |
| OpenAI planner | PASS | 1465.48–1465.48 |
| OpenAI RAG | PASS | 2348.80–2348.80 |
| Qdrant query | 29 points / 384 dims / Cosine / expected model sample verified | 53.91 |
| LangSmith | 18 traces inspected | 9606.59 (includes ingestion wait) |

| Scenario | Fallback priority | Live priority | Live planner | Live workflow ms |
|---|---:|---:|---|---:|
| JUDGE-001 | 0 → 0 | 0 → 0 | LIVE | 5938.68 |
| JUDGE-002 | 35 → 35 | 35 → 35 | LIVE | 9023.47 |
| JUDGE-006 | 40 → 0 | 40 → 0 | LIVE | 8818.03 |

Artifacts: `fixtures/live_judge/manifest.json`, `fixtures/live_judge/documents/`,
`results/live_judge/report.json`, `results/live_judge/report.md`,
`results/live_judge/bugs/LJG-001.md` through `LJG-005.md`,
`tests/live_judge/test_regressions.py`, and `docs/live_judge/README.md`.

ROUND 2 REQUIRED: **YES**. Branch is RED_UNRESOLVED. Do not merge. No production fixes.
