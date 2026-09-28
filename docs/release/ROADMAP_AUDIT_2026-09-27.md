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

## Source-backed confirmation delivery

- Full baseline at `12011b8`: `python -m pytest tests -o addopts= -q --tb=short` → 533 passed, 1 failed in 841.15s. Failure: first Streamlit AppTest exceeded its existing 10-second startup timeout. Exact isolated rerun passed (1 passed); do not describe the original run as green.
- Native allocation extraction reads labelled company, transaction, line and proposed project quantities from the actual PDF. It never uses filename/fixture identity or expected case fields. Unsupported layouts stay on the manual path; conflicting repeated fields remain ambiguous.
- The company API now exposes `POST /api/cases/{case_id}/transcriptions/{proposal_id}/confirm`. The company document screen exposes its form. Corrections are applied, unsupported values lose supporting spans, and the new score is stored atomically with the confirmation revision.
- Public API regression proves 20 → 10 → 20 → 10 → 0, source recovery, company/officer isolation and idempotent retry. The existing quantity workflow proves 40 → 30 → 20. Pure tests cover 10 → 20 → 30 → 40; these are not a claim that all rollback actions already have UI controls.
- `npm test -- --reporter=dot`: 23 passed; TypeScript/build passed. `BOUSSLA_E2E_URL=http://127.0.0.1:8018 npm run test:e2e -- demo.spec.ts`: 1 passed, including visible 20 → 10 → 0 through company confirmation and officer acceptance.
- Limitations: allocation native layout only; no universal PDF/OCR or authenticity guarantee. Settlement/counterparty evidence replacement and broad document analysis remain later roadmap work. Existing Streamlit timeout needs monitoring on a warm complete rerun.

## Five-indicator contract

The officer API now exposes `indicators` with exactly document review, evidence coverage, historical signal, urgency and operational confidence. Each provides value/status/factors/explanation/calculated_at/rule_version/sample_size. Existing numeric fields remain compatible; no new blended score is introduced. Company responses do not contain this object. French urgency factors identify their source requests, proposals or history signals. Backend integration: 27 passed, plus 13 passed after source-label refinement. TypeScript passed.

## Confidence consolidation

`OPERATIONAL_CONFIDENCE_V3` keeps the approved 30/25/25/20 normalized dimensions, but counts distinct requests, reviewed documents and covered transactions for the minimum three-observation threshold. A response participating in two dimensions no longer fabricates a third sample. Observations are restricted to twelve months at the declared cutoff; missing decision timestamps use the associated response date only when available. Numeric results from fewer than ten distinct observations carry LIMITED_DATA and a French count/window explanation; the ten-observation display threshold is a demo convention, not statistical certification. Targeted confidence/history/progression/release tests: 37 passed; TypeScript passed. No impact on documentary score or urgency.

Complete rerun at a95cd0c: 539 passed, 1 failed in 770.16s; the same first Streamlit startup exceeded ten seconds. Initial-render allowance is now 30 seconds; subsequent interactions keep the ten-second budget and all assertions remain unchanged. Confidence final follow-up: 22 passed.
Startup adjustment verified: all six tests in tests/ui/test_app.py passed in 38.14s. A complete rerun after this adjustment remains outstanding.

## Own-company baseline increment (phase 4 remains partial)

Officer-only behavior_profile exposes the last completed observation month and up to six covered prior months, with at least three usable months required for comparisons. Invoice counts, supplier counts, deposit delays, currency-separated amounts and dispersion, observed payment splits, response delays, reviewed-document rejection, confirmation activity and new suppliers have explicit provenance. Ambiguous buyer observations invalidate their month instead of silently selecting the first. Seasonal comparison requires two covered homologous annual months. Missing cash mode, unavailable historical findings and insufficient event observations remain unknown. This descriptive profile does not affect documentary scoring. Runtime history cache now keys the requested cutoff, preventing reuse of later calculations for earlier dates. Validation: 25 targeted backend tests, TypeScript and 24 React tests passed. Broader anomaly history and actual correction-only counts remain pending; this is not phase-4 completion.

## Historical measurement follow-up

`self-baseline-2` supports explicit payment methods (old records default to UNKNOWN), correction-only events and evaluated unresolved causes grouped by transaction period. The case service evaluates those findings at the profile cutoff. Cause counts describe the state calculated at that cutoff, not an archived history of past decisions. Correction writes retain before/after values, actor, time and rule in the versioned confirmation record, with a distinct TRANSCRIPTION_CORRECTED event. Plain legacy confirmations never count as corrections. Payment methods remain absent in the frozen V1 synthetic fixture, whose serializer explicitly preserves its schema. Validation: 79 operational-portfolio/progression tests and 9 focused baseline tests passed. Unknown values remain when payment modes or correction events are not available; no false certainty is substituted.

## Reconciliation increment

Five explicit reconciliation states now distinguish absent observations, awaiting counterpart, ambiguous candidates, differences and matched observations. No first-candidate selection: multiple buyer/seller observations remain ambiguous. Independent scoped provenance and confirmed fields are required for a match. Every uniquely identifiable line is compared, with decimal normalization and reordered-line matching; duplicate item keys remain ambiguous. The scoring check detects second-line differences and reports V4-INVOICE-2 for multi-line inputs; single-line V1 calculations remain compatible. Snapshot rules_version now lists actual finding rule versions instead of the generic B fallback. Explicit payment, delivery and project relationships use only canonical transaction links. React displays all lines and ambiguous candidates. Validation before relationship follow-up: 81 backend tests, production build and 24 React tests passed.

Complete suite launched at 6b0fcde: 552 passed in 437.94s, including the stabilized Streamlit cold start. Reconciliation relationship/version follow-up: 52 backend/service/progression tests passed.

## Document pipeline increment

Each accepted upload now persists a ten-stage document analysis report in the same revision as its recalculation; confirming or correcting fields replaces that report in the new revision. Native title classification covers invoice, payment, delivery, allocation, contract, declaration and unknown. A conservative labelled-field fallback extracts explicit native values and verifies source spans. Checks cover sums, line arithmetic, declared tax arithmetic, dates, duplicates/references, company scope, candidate transaction links, dossier and response concordance, metadata chronology and byte integrity. Cause links are proposals restricted by transaction and document family; the report never resolves a cause. Company responses expose processing state but omit the internal report and cause identifiers. External registries and visual tamper detection are explicitly UNKNOWN; OCR/universal layouts remain unsupported. This is a functional native-document pipeline, not universal documentary analysis. Validation: 69 backend/document/progression/routing tests, TypeScript and 24 React tests passed. Invalid adapter source spans are rejected without a case revision.

## Document confidence

Document reports now persist a deterministic quality-of-analysis index with four explicit dimensions: extraction completeness, executable internal checks, dossier/response concordance and byte conservation. The 35/30/25/10 weights are normalized over measured dimensions only, with a minimum of three dimensions. Unknowns remain null. Failed checks cap the value at 39 and warning signals at 59. Labels and explanations explicitly distinguish this demo rule from statistical extraction accuracy or authenticity probability; byte integrity never asserts absence of manipulation. The index is officer-only and never changes scoring or acceptance. Validation: 30 document/progression tests, TypeScript and 24 React tests passed.

## Cause-scoped questionnaire

The controlled catalogue remains capped at three questions per cycle. It now includes typed amount/date and response-plus-document questions for settlement; server-side schemas validate number/date/choice and a 2000-character limit. Questions carry a single transaction scope and neutral context. A response cannot provisionally reduce another transaction merely because the request also mentions it; document-only answers to scoped file questions are supported. The planner now considers unresolved causes even when another transaction in the same family is explained. Automatic requests suppress duplicates across covered cause scopes. A matching already-open request is reused idempotently; a different concurrent publication is rejected, while an officer may deliberately ask again after a response or rejection. Rule version progressive-review-3 records this linkage change. Validation: 61 service/context/question tests, 26 targeted progression/question tests, 18 workflow tests, TypeScript and 24 React tests passed. The existing AI assistant only chooses allowlisted catalogue IDs; free-form model-authored wording is not authoritative.

## Recommended actions

The officer case view now computes a bounded, priority-ordered list from pending evidence proposals, analyzed documents, open/overdue requests and cause stages. Each action has a stable ID, priority, explicit reason, cause/document sources, required document classes where applicable and OPEN/WAITING status. Coherent provisional evidence requests human validation; rejected evidence prompts a replacement document; an existing request instructs the agent to wait or follow up rather than publish another. The read model has no side effects and is absent from company views. Validation: 51 service/progression tests and production build passed; React tests are completing.

## Navigation agent et entreprise

L’espace agent présente désormais Dashboard, Dossiers, Réseau, Historique, Notifications et Avancé. Les références, la timeline et les diagnostics restent accessibles depuis Avancé. L’espace entreprise présente Mes dossiers, Actions requises, Documents et Messages ; son écran d’accueil conserve le contexte et les opérations en lecture ciblée. Les vues Réseau et Notifications sont des premiers points d’accès aux données existantes ; les API réseau typées et les notifications persistantes restent respectivement en phases 17 et 14. La page Dossier actuelle n’est pas encore la synthèse en six zones de phase 11. Une assertion Playwright a été précisée pour distinguer le libellé confidentiel de la phrase explicative visible par l’entreprise. Validation : 25 tests React, compilation TypeScript/production et parcours Playwright principal sur base synthétique isolée (1 passé).

## Six-zone dossier page

The officer dossier now orders synthesis, cause contributions, evidence counts and source analyses, recommended actions, revision timeline and human decisions. Evidence counts distinguish available documents, analyzed documents awaiting review and requested document types; they do not claim all absent documents are known. The timeline is loaded from the immutable history API and tolerates an incomplete response without crashing the page. Decision controls retain existing source and version checks. Historical metrics, documentary detail and investigative simulations are available in labeled disclosures so the main path remains readable. This is a presentation refactor, not a new scoring rule or a general accept/reject/escalate decision model. Validation: 26 React tests (including ordered sections), TypeScript/production build and fresh synthetic Playwright main journey (1 passed).

## Company action cards

The company overview now shows currently published requests as justification tasks with a direct route to the response form. When no context has been declared, it offers a direct link to the declaration form. A document awaiting review is described as automatically analyzed and awaiting agent validation; a company with no open response request is told so. The cards derive from the company-scoped inbox, context and document processing states rather than fixed instructions. This does not add messaging delivery outside the local demo. Validation: 27 React tests, TypeScript/production build and fresh synthetic Playwright main journey (1 passed).

## Source-backed dossier timeline

The officer timeline now renders every stored revision with its timestamp and associated events in time order, including event actor and fact IDs when present. Adjacent frozen score snapshots show review-index and per-cause contribution transitions; absent snapshots produce no invented transition. The main browser journey verifies the recorded 10 → 0 after agent acceptance. Older and some non-scoring revisions lack snapshots, so the timeline cannot yet show every intermediate index transition. Validation: 28 React tests (including 40 → 30 and a missing-snapshot case), TypeScript/production build and fresh synthetic Playwright main journey (1 passed).

## Internal notifications

A per-case API projects internal notifications from durable case events and adjacent frozen score snapshots. The officer sees uploads, completed document analysis, responses, decisions and recorded score changes. The company sees only its own document analysis, its confirmed fields and published requests; internal score and officer decisions remain hidden. The feed is ordered, bounded to 100 and explicitly labeled RECORDED, not an unread/read state. The agent Notifications screen and company Messages screen display it; recommended actions remain a separate current-work list. No email/SMS, delivery scheduler, deadline trigger, read receipt or persistence beyond underlying events is claimed. Validation: 39 backend/API tests, 28 React tests, TypeScript/production build and fresh synthetic Playwright main journey (1 passed).

## Impact if resolved

The officer view now returns sequential, hypothetical cause-resolution impacts. Each step removes only one still-active cause, carries prior hypothetical resolutions forward and recalculates the maximum transaction index with the same progressive rounding rule. Unchanged other transactions can keep the dossier index elevated. The simulator refuses to display steps when its baseline cannot reconstruct the recorded current index, never writes a fact, and is omitted from company views. Source IDs, case version, calculation time and rule version accompany each step; the UI states that no change has been applied. Validation: 55 scoring/service tests including two-transaction 40 → 30 → 0 and baseline mismatch, 29 React tests, TypeScript/production build and fresh synthetic Playwright main journey (1 passed).

## Historical dashboard

The dedicated officer Historique view now leads with each own-company baseline metric: observed period, baseline average, percent change when computable, sample size, calculation method and source IDs. Its monthly chart renders UNKNOWN coverage as unknown rather than a zero transaction bar. Invoice, payment, signal and revision details remain below the comparison. The service's existing covered-month baseline is reused without changing documentary scoring. Validation: 30 React tests, TypeScript/production build and a fresh synthetic Playwright test that compares rendered current/baseline values with the officer API (1 passed).

## Network model and API

An officer-only, source-attributed graph now exposes GET /api/network, /api/network/company/{id} and /api/network/case/{id}. Nodes include company, case, transaction, invoice observation, payment, document, project and recorded delivery. Edges include canonical buyer/seller and project links, recorded issuer/receiver/document links, and PAID only for an accepted payment allocation. Every edge carries fact IDs and a provenance status; invoice observations stay distinct instead of being silently merged. The service reads only assigned cases, rejects company access and unknown scopes, and omits local file paths. The Réseau page consumes this backend graph as a sourced relationship list; interactive 3D remains phase 18. Validation: 43 backend/API tests, 30 React tests, TypeScript/production build and fresh synthetic Playwright network journey (1 passed).

## Interactive 3D network

The agent Réseau page now projects stable 3D node positions to an interactive canvas with pointer rotation, wheel/button zoom, company search, date and amount filters, and a current-case finding filter. Node and edge selection shows recorded case, observation, amount, confidence-availability and source details; accessible button lists provide equivalent selection without canvas hit testing. The default scope is the current dossier because the full synthetic portfolio has 1,181 nodes and 2,440 edges; the agent can switch to all assigned dossiers. Positions are navigational only. Period and minimum amount filters apply to dated/valued facts, and finding filtering is limited to the current dossier. Pairwise historical growth is shown as unavailable rather than invented. No dependency, score rule or fraud inference was added. Validation: 30 React tests, TypeScript/production build, fresh synthetic Playwright network journey (rotation, zoom, filters, node/edge selection, isolation) and desktop visual inspection.

## Cited investigation assistant

An officer-only POST /api/cases/{id}/investigate answers bounded questions from the current case causes and urgency, own-company baseline, recommended documentary actions, scoped network, candidate public references and recorded decisions. Responses include visible source IDs/URLs, case version, rule version, TEMPLATE mode and a human-review limitation. Unsupported questions fall back to sourced case context or an explicit insufficient-data answer. No case fact is written; model-authored free text is not accepted as authority. This is structured evidence retrieval plus deterministic synthesis, not semantic search over every PDF or an autonomous applicability decision. Validation: 46 backend/API tests, 31 React tests, TypeScript/production build and fresh synthetic Playwright investigation journey (1 passed).

## Durable decision audit

Every new case event now writes a linked audit row inside the same SQLite transaction. The officer-only `GET /api/cases/{id}/audit` returns actor, action, time, reason, case version, linked fact/proof IDs and the available before/after documentary score and per-cause contributions, with rule and engine versions. Human evidence acceptance/rejection passes both evaluated snapshots explicitly, so a 20 → 0 decision remains attributable even when the prior revision has no frozen score. Identical idempotent retries create no duplicate audit entry; rollback removes both event and audit row. Existing databases add the table without altering historic events, which are counted as legacy gaps. Missing historical or non-scoring snapshots remain null. This is a local traceability journal, not tamper-proof legal evidence; events before this migration cannot be retroactively enriched. Validation: backend store and HTTP contract tests including rollback, migration, access control, score transition and retry.

## Full-suite stabilization after phase 21

The complete backend suite passes (599 tests), React passes (31 tests), the production frontend builds, and all 11 Playwright journeys pass against a fresh isolated synthetic database. Four browser assertions initially failed after the navigation redesign and a prior test's accepted evidence changed the shared case state: assisted analysis needed its disclosure opened, Company 360 needed its Historique navigation, the invoice comparison label had changed, and the investigation assertion assumed a fixed initial review index. The tests now assert the current interface and the case score returned by the officer API. The full suite rerun is green; the initial failures were real release-check drift, not a scoring regression.

## Frozen snapshots on every versioned workflow write

Context declarations, structured answers and officer-published clarification requests now freeze a documentary `ScoreSnapshot` at their new case version, as upload, response and human evidence decisions already did. Each snapshot records calculation time, engine/rule versions and cause contributions. The prospective score uses only scoped facts from that revision, including the new attributed claims or request; replayed idempotent actions do not create another revision. A newly created empty case still has no document cause to calculate, and older revisions remain honestly unsnapshotted. Validation: targeted service/progression/API tests assert snapshot metadata for all three paths.

## Officer audit journal in the dossier

The Advanced agent view now exposes the officer-only audit API in a case-version-keyed panel. It shows event/action, actor, time, reason, linked source IDs, documentary review-index before/after, changed cause contributions, rule version, engine version and any count of legacy events that lack the newer audit row. The panel makes no legal-integrity claim. Its query refreshes on case mutations and the version key avoids a stale cached journal after a human decision. Validation: 31 React tests, production build and a clean main Playwright journey that accepts evidence and verifies the persisted 10 → 0 score and cause transition in the audit panel.

## Document-grounded investigation answers

A document-specific investigation question now retrieves the stored officer-side analysis report for the named document (or a bounded set of analyzed documents). It states proposed class, documentary confidence, non-passing/unknown checks, linked causes, source IDs and the explicit authenticity-to-verify statement. The answer cites the document/report rule and each available control source. Generic missing-document questions continue to use recommended actions. It remains deterministic and read-only; no semantic PDF indexing, external authenticity verification or autonomous fraud conclusion is claimed. Validation: officer-only document retrieval and existing network/decision answer tests.

## Explicit own-company deviations

`self-baseline-3` adds descriptive, source-backed historical signals when a covered month’s mean response delay or currency-specific invoice amount is at least 2× its own-company baseline. Every signal records current and baseline values, ratio, three-or-more covered baseline months, current observation count, rule version and only sources in the compared periods. Fewer than three current observations yields LIMITED_DATA and a visible caveat. Signals appear before the detailed Historique metrics and can be cited in a historical investigation answer. They neither alter documentary review scoring nor assert fraud. Months without adequate coverage/baseline produce no signal. Validation: 67 operational portfolio tests, 601 complete backend tests, 31 React tests, production build and fresh historical Playwright journey (1 passed). This closes the requested explicit examples for measured delay and amount deviations; provenance gaps in synthetic payment modes remain UNKNOWN.
