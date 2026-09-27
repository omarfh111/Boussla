# Roadmap audit and delivery ledger

The user authorized the expanded phases 0–21 on 2026-09-27 and requested one-line atomic commits followed immediately by branch pushes. This supersedes the old eight-hour feature scope, but preserves provenance, audience isolation, source validation and human acceptance safeguards. Continue the existing `feat/progressive-review` branch; never push main.

## Starting state

HEAD d099759, two commits ahead of origin. Existing uncommitted confidence/history corrections were preserved and reviewed. No secrets or runtime databases are deliverables.

| Phase | Initial state | Evidence / remaining acceptance |
|---|---|---|
| 0 Audit | PARTIAL | React 23 passed; Python initially blocked by missing Streamlit; full rerun and browser verification pending. |
| 1 Progressive scoring | PARTIAL | Pure stages and 40/30/20/10/0 integration exist; coherence test directly writes extraction facts. Transcription confirmation lacks a score snapshot; cause resolution metadata and granular rollback need coverage. |
| 2 Five indicators | PARTIAL | Separate outputs exist; shared metadata contract missing. |
| 3 Operational confidence | PARTIAL | Pending correction implements approved 30/25/25/20 dimensions, unknown-data threshold, factor deltas. Latest complete suite not yet verified. |
| 4 Advanced history | PARTIAL | Covered-month baseline, delays, amounts, suppliers, split payments; full requested metric inventory not implemented. |
| 5 Reconciliation | PARTIAL | Deterministic comparisons and source independence; complete explicit matching lifecycle not verified. |
| 6 Document pipeline | PARTIAL | PDF extraction/routing/integrity adapters; complete per-upload causal analysis not implemented. |
| 7 Document confidence | MISSING | No complete separate explanatory indicator. |
| 8 Questionnaire | PARTIAL | Bounded catalogue and clarification loop; complete typed cause-driven workflow missing. |
| 9 Recommended actions | PARTIAL | Existing guidance; structured lifecycle needs audit. |
| 10 Agent journey | PARTIAL | Existing screens; requested navigation not implemented. |
| 11 Dossier page | PARTIAL | Indicators and contributions present; new six-zone layout missing. |
| 12 Company journey | PARTIAL | Scoped responses/uploads; requested simplification missing. |
| 13 Timeline | PARTIAL | Revision/event history exists; complete cause-level narrative missing. |
| 14 Notifications | MISSING | Dedicated internal notification workflow missing. |
| 15 Resolution impact | PARTIAL | Noncanonical scenarios exist; sequential per-cause impact workflow missing. |
| 16 Historical dashboard | PARTIAL | Monthly context exists; habit versus current dashboard missing. |
| 17 Network model | MISSING | Typed scoped network API missing. |
| 18 3D graph | MISSING | Build only after network API and main journey verification. |
| 19 Network intelligence | DEFERRED | User schedules after Tuesday; no fraud inference. |
| 20 Investigation RAG | PARTIAL | Existing sourced reference assistant; unified case/history/network evidence missing. |
| 21 Audit | PARTIAL | Versioned facts, action receipts and events; complete before/after/rules/engine attribution missing. |

## Initial findings

- The frozen V1 portfolio evaluation changed solely because additive runtime transaction attribution was serialized into it. Preserve the V1 report schema explicitly; do not regenerate its oracle to hide a regression.
- A confirmed extraction is currently marked confirmed without applying corrected field values; this must be checked before it can grant EVIDENCE_COHERENT.
- Coherence is implemented for allocation proposals only. A passing quantity example does not prove settlement/counterparty progression.
- Existing 522-Python/22-React claims belong to an earlier state and are not evidence for this checkout.

## Delivery policy

Work in requested order. Before each production increment: meaningful regression tests, explicit staged paths, diff review, one-line commit (no trailer), immediate push and remote SHA verification. Record failures as failures. Unknown authenticity and unsupported OCR remain explicit; never invent confidence or source facts.

## Verified increments

- `0eec222` pushed and remote SHA verified: normalized confidence, attributed history, calendar coverage and preserved V1 evaluation serialization. React: 23 passing; main Playwright journey: 1 passing on offline port 8017. The first 147-test targeted backend run had 146 passing and one frozen-report failure; all 24 V1 history tests passed after the serializer correction.
- Progressive review regression scope: `python -m pytest tests/backend/test_services.py tests/backend/test_final_automation.py tests/integration/test_progressive_review.py tests/checks/test_review_progress.py -o addopts= -q` → 92 passed. Follow-up scoped suite with unrelated-transaction regression → 23 passed.
- New rules `progressive-review-2`: blank explanations grant no reduction, accepted residual findings receive no provisional discount, reason codes alone cannot link unrelated transactions. Persist cause IDs, initial weight, supporting IDs, decision actor/time and rule/engine/cutoff metadata. Explicit historical evaluation returns the recorded snapshot.
- UI exposes original/current contribution, human validation requirement, rule and resolution attribution. `npm test -- --reporter=dot`: 23 passed; `npm run build`: passed; `npm run format:check`: passed.
- `python -m pip install -r requirements.txt` installed the existing lock; pip reported incompatibilities with unrelated packages in the shared user Python installation. No dependency lock was changed. The complete project suite is running; its result is not yet known.

The additional fields are backward-compatible defaults for old saved records. The enum remains `UNRESOLVED` (the requested DETECTED meaning) to preserve clients. Historical snapshots from previous engines are retained, not relabelled as the new method.
