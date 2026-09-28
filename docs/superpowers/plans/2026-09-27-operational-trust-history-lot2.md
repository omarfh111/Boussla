# Lot 2 — historique propre et confiance opérationnelle

Branch: `feat/progressive-review`. This plan follows the completed Lot 1 plan and keeps the documentary score backend-owned and independent of historical/behavioral indicators.

## Contract

- Historical observations compare an enterprise to its own covered baseline. Missing coverage and a covered zero month remain distinct. A signal requests review; it is never an allegation or an automatic documentary finding.
- The historical signal index is a separate 0–100 review-context indicator with visible source signals and contributions. No baseline means `null` / `INSUFFICIENT_DATA`.
- Operational confidence is a reversible 0–100 index computed only from attributable workflow events and covered history. It exposes factor contributions, sample counts, a method version, and `INSUFFICIENT_DATA` when too little evidence exists. Neither index enters `ScoreSnapshot.review_index` or evidence acceptance.
- The API owns every formula and threshold. Frontends render values, states and factors only.

### Task 1: Extend self-history signals

**Files:** `boussla/history_signals.py`, `boussla/contracts.py`, tests in `tests/checks/test_history_signals.py` and portfolio integration.

- [ ] Add failing tests for company-specific invoice delay baseline, amount change, first-seen supplier, unusually split payments, and repeated contradictions. Test missing coverage, mixed currency and distinct transaction scope.
- [ ] Implement deterministic neutral signals from covered periods and source IDs; do not mutate the documentary score.
- [ ] Run relevant checks and portfolio tests; commit.

### Task 2: Historical indicator with contributions

**Files:** New `boussla/historical_indicator.py`; `boussla/contracts.py`, `boussla/services.py`; checks and integration tests.

- [ ] Define a pure indicator from already derived `CompanyHistorySignal`s with bounded contributions and explicit missing-data policy; tests first.
- [ ] Expose index/status/contributions in the officer case and queue, preserving company exclusion and `review_index` exactly.
- [ ] Verify triage reasons are explainable and no history signal silently alters documentary score; commit.

### Task 3: Operational confidence with attributable factors

**Files:** New `boussla/operational_confidence.py`; `boussla/contracts.py`, `boussla/services.py`; checks and integration tests.

- [ ] Define sufficient-data threshold and factors for response timeliness, answered/pending requests, accepted/rejected proposals, answer/document consistency, repeated anomalies and covered historical behavior.
- [ ] Test reversibility on answer, rejection, later accepted evidence, missed target, and a new contradictory proof. Test insufficient-data and scope isolation.
- [ ] Return index/status/factor list/sample counts to the officer API only. Keep the documentary score unchanged; commit.

### Task 4: UI and release gate

**Files:** `frontend/src/api/types.ts`, `frontend/src/App.tsx`, `frontend/src/styles.css`, React tests, README and release report.

- [ ] Show the backend's historical and trust contributions, 12-month behavioral context and missing-data labels without client calculations. Add a focused company exclusion test.
- [ ] Run all Python, frontend, build and available browser checks; document actual outcomes and limits, commit and push.

## Next

Lot 3: per-document classification/extraction/verification and buyer–seller matching. Lot 4: adaptive questionnaires and recommended actions. Lots 5–7: simplified agent/company dossier journeys, notifications, timeline and impact. Lots 8–11: historical dashboard and network graph from 2D to 3D with analytics.
