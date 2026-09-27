# Progressive Review Lot 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a versioned, backend-owned review index that changes by cause through 40 → 30 → 20 → 10 → 0, can rise after contradiction, and is explained in the current officer dossier.

**Architecture:** Keep the existing deterministic `Finding` and 35/25/40 baseline. A pure progress module derives cause stages from versioned case facts and returns current contributions; the service persists score snapshots and exposes them only to officer views. React renders the returned stage and numbers without arithmetic.

**Tech Stack:** Python 3.12, Pydantic, SQLite, Starlette, pytest, React 19, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-progressive-review-indicators-design.md` (this plan implements its progressive review and existing-dossier presentation; the confidence and historical extensions get the next plan).

## Global Constraints

- The frontend never calculates a score or chooses a progression stage.
- Only a resolved deterministic cause after scoped officer acceptance can reach `RESOLVED` / zero; earlier stages are provisional.
- A contradiction or rejected evidence can move a cause backward and raise the index.
- Company responses remain attributed claims; document receipt and technical consistency do not prove authenticity.
- Historical signals, evidence coverage, urgency and confidence remain distinct from documentary review.
- Preserve the company API's exclusion of internal indicators, SQLite version checks and idempotency.
- Use synthetic fixtures; no live provider call is required for tests.

## Review Focus

1. A response unrelated to a finding must not lower its contribution (Task 2 test).
2. A company-supplied second invoice must not count as independent seller corroboration (Task 3 regression test).
3. A technical consistency stage based only on a hash or model class must be refused (Task 2 test).
4. A tiny unresolved contribution must remain at least 1 after rounding (Task 1 test).
5. Officer-only cause data must not leak through the company API (Task 3 test).

---

### Task 1: Pure cause-stage calculator

**Files:** Create `boussla/review_progress.py`; modify `boussla/contracts.py`; test `tests/checks/test_review_progress.py`.

**Interfaces:** Consume `Finding`, `FindingFamily`, `FindingStatus`; produce `ProgressStage`, `CauseProgress`, `ProgressEvidence`, and `calculate_progress(findings: tuple[Finding, ...], evidence: tuple[ProgressEvidence, ...]) -> tuple[CauseProgress, ...]`. `ProgressEvidence` names the transaction, family, response/document/proposal IDs, verified consistency, officer outcome and contradiction reason. `CauseProgress` gives raw/current decimal contributions, source IDs, reason and provisional status.

- [ ] Write tests for the five stages, proportional weights 35/25/40, distinct cause keys, contradiction regression, and minimum unresolved index 1.
- [ ] Run `python -m pytest -p no:cacheprovider --basetemp test-tmp-progress tests/checks/test_review_progress.py -q`; expect failures because the new API is absent.
- [ ] Implement the pure calculation with explicit 100/75/50/25/0 percent factors and no clock, store, network or model access.
- [ ] Run the targeted test command; expect all new tests to pass.
- [ ] Commit the calculator, contract and tests as one coherent change.

### Task 2: Derive evidence stages from one case version

**Files:** Create `boussla/review_evidence.py`; modify `boussla/services.py`, `boussla/web/app.py`; test `tests/integration/test_progressive_review.py` and `tests/web/test_api_boundaries.py`.

**Interfaces:** Produce `derive_progress_evidence(findings, facts, previous_snapshot) -> tuple[ProgressEvidence, ...]`. Extend `upload_document` with optional `response_id` so a document can be attached after an initial answer in the same versioned upload; an attached allocation proposal receives that document ID. Keep the old upload call valid.

- [ ] Write a service test that starts at 40, submits a linked answer without a document (30), then uploads a scoped PDF linked to that answer (20). Add tests for unrelated answers, foreign/duplicate documents and idempotent retry.
- [ ] Run the new test; expect the stage or upload-link API assertions to fail for missing behavior.
- [ ] Implement strict, versioned response/document/proposal linking and derive stages from stored facts; preserve old endpoints and limits.
- [ ] Run targeted service and API-boundary tests; expect all to pass.
- [ ] Commit the association behavior with its tests.

### Task 3: Score snapshots, coherence and reversibility

**Files:** Modify `boussla/services.py`, `boussla/contracts.py`, `boussla/store.py` only if necessary; test `tests/integration/test_progressive_review.py` and `tests/integration/test_final_release.py`.

**Interfaces:** Extend `ScoreSnapshot` additively with `raw_review_index`, `cause_progress` and `decisive_transaction_id`. `review_index` is the max transaction's adjusted index; legacy `contributions` remain raw. A deterministic coherence assessment uses scoped proposal fields plus source-backed extracted or confirmed document fields; uncertainty remains at `EVIDENCE_RECEIVED`.

- [ ] Write tests for 40 → 30 → 20 → 10 → 0, contradiction 10 → 40, rejected evidence regression, resolved and residual acceptance, old revision snapshots and company-view exclusion.
- [ ] Run the targeted tests; expect failure in new score/stage assertions.
- [ ] Wire the pure calculator into `_evaluate`, persist snapshots on relevant revisions, and return a version-consistent officer/queue score. Never force a zero after acceptance.
- [ ] Run targeted integration and web isolation tests; expect all to pass, including existing score baselines without provisional evidence.
- [ ] Commit the backend integration and tests.

### Task 4: Explain the five indicator slots in the current dossier

**Files:** Modify `frontend/src/api/types.ts`, `frontend/src/App.tsx`, `frontend/src/styles.css`; test `frontend/src/test/app.test.tsx`.

**Interfaces:** Render the backend's `cause_progress` rows (raw/current/stage/reason/provisional) and separately label review, coverage, historical context, urgency and operational confidence. Until Lot 2 computes confidence, the backend returns `null` / `INSUFFICIENT_DATA`; React does not invent 0 or a default number.

- [ ] Write a React test that feeds an officer case with a provisional 40 → 20 cause and asserts the displayed values, labels and reason; verify the company view has no indicator panel.
- [ ] Run `npm --prefix frontend run test`; expect the new assertion to fail before the UI change.
- [ ] Implement only the summary strip and cause explanation in the existing dossier layout, using numbers and labels from the API.
- [ ] Run frontend tests, typecheck, format check and production build; expect all to pass.
- [ ] Commit the UI changes and tests.

### Task 5: End-to-end release gate for Lot 1

**Files:** Update `README.md` and `docs/release/FINAL_RELEASE_REPORT.md` with the new method and actual test evidence only; add a focused browser journey in `frontend/e2e/journeys.spec.ts` if the existing test server can exercise it offline.

**Interfaces:** No new API; verify the complete backend-owned 40 → 30 → 20 → 10 → 0 journey and document the distinction between raw, provisional and accepted values.

- [ ] Add the browser assertion for the explanation panel or an equivalent API end-to-end test with persisted revisions; watch it fail before the final wiring, if any remains.
- [ ] Fix only uncovered release wiring, then run full Python tests, frontend tests/typecheck/build and the available browser journey. Record actual counts and any environment-limited checks.
- [ ] Update documentation with commands and observed results, inspect the staged diff and commit the release slice.
- [ ] Push the tested branch to `origin/feat/progressive-review` and verify the remote SHA matches HEAD.

## Next plans

Lot 2: operational confidence and broader self-history baseline. Lot 3: per-document analysis and buyer/seller matching. Lot 4: adaptive questionnaire and fact-based actions. Lots 5–7: agent/company journeys, notifications, timeline and impact. Lots 8–11: historical dashboard, validated 2D network, 3D investigation and later network analytics. Each lot reuses the same backend-owned indicators.
