# Shared contract/dependency changes

Only A approves and merges changes. Record: requester, proposed change, reason, affected consumers, migration, tests, decision and timestamp. No open requests at pack creation.

## CR-001 — align `DocumentClass` with Jev routing categories (A, applied)

- **Requester / decider:** A (self-identified mismatch), 2026-09-25.
- **Change:** `boussla.contracts.DocumentClass` members are now exactly the Jev Choice categories in `config/prompt_templates.md`: `INVOICE`, `PAYMENT_RECORD`, `ALLOCATION_REFERENCE`, `ALLOCATION_RESPONSE`, `DELIVERY_RECORD`, `CREDIT_NOTE`, `OTHER_OR_UNKNOWN` (was `PAYMENT`, `ALLOCATION`, `DELIVERY`).
- **Reason:** one enum for router output, allowed clarification document types and UI labels; avoids a C-side mapping table.
- **Consumers:** C (router output), D (allowed document types display). Published before any consumer merged code.
- **Migration:** rename references; no stored data exists yet.
- **Tests:** `pytest` full suite.

## CR-002 — officer-only grounded reference note (A, applied)

- **Requester / decider:** A, for lane C integration (`integration/reference-retrieval`), 2026-09-26.
- **Change:** new `GroundedNoteView` (summary_fr, candidate_rule_ids, applicability_questions, limitations, provider_model, generation_mode, disclaimer_fr) and `OfficerCaseView.reference_note: GroundedNoteView | None = None`. `CompanyCaseView` unchanged, with no equivalent field.
- **Reason:** C's `GroundedReferenceNote` is a dataclass internal to `boussla.retrieval`; D needs a typed, officer-scoped view to render "Synthèse assistée à partir des passages retrouvés".
- **Consumers:** D (optional rendering). Backward compatible (optional, default None).
- **Tests:** `tests/integration/test_reference_service.py`.

## CR-003 — shared project-horizon types for context consistency (A, applied)

- **Requester / decider:** A, for lane C integration (`integration/context-consistency`), 2026-09-26.
- **Change:** `HorizonBucket` (SHORT_HORIZON / LONGER_HORIZON / UNKNOWN) now lives only in `boussla.contracts`; `boussla.context.models` re-imports it (one definition, no import cycle). `ContextClaim.declared_horizon: HorizonBucket = UNKNOWN` (explicit company declaration only). New `ContextAssessmentView` (declared / interpreted / calculated horizon and purpose, duration, consistency status, reason codes, recommended question IDs, validated spans, corroboration NOT_ASSESSED, interpretation mode, horizon convention text), exposed as optional `context_assessment` on both `CompanyCaseView` and `OfficerCaseView`.
- **Reason:** C's context layer needs a company-confirmed horizon and a typed presentation contract for D.
- **Consumers:** D (React: Déclaré / Interprété / Calculé / Cohérence). All fields additive with safe defaults; stored claims without the field load as UNKNOWN.
- **Tests:** `tests/integration/test_context_service.py`.

## CR-004 — final automation core: strict inputs, automatic clarification, triage (A, applied on `feat/final-automation-core`)

- **Requester / decider:** A (final sprint; judge round 1 defects LJG-001..004), 2026-09-26.
- **Change (additive, version `boussla-automation-1`):** `ErrorCode.INVALID_INPUT`; `ClarificationRequest.origin` (default `OFFICER`); new `ClarificationDeadlineView`, `TriageAssessment`, `HistorySignalKind`, `CompanyHistorySignal`, `InvestigatorBriefPoint`, `InvestigatorBrief`; protocols `CompanyHistorySignalProvider` (B) and `InvestigatorBriefProvider` (C); optional `OfficerCaseView.triage / clarification_deadlines / history_signals / investigator_brief`; optional `QueueItem.triage_priority / triage_reason_codes`.
- **Behaviour:** documentless proposals cannot be accepted; context/response/allocation payloads are strict (typed errors, no silent drops); automatic neutral clarification in the submission's own revision; queue ordered by triage urgency. `review_index` unchanged in meaning and computation.
- **Consumers:** B (implement `CompanyHistorySignalProvider`, pass it as `history_signal_provider=`), C (implement `InvestigatorBriefProvider`, pass as `investigator=`), D (optional: label `origin=AUTOMATIC` requests, show triage reasons, hide "Accepter" when `source_document_id` is null, label `FOLLOW_UP_DUE`). All fields optional with safe defaults; stored requests load as `OFFICER`.
- **Tests:** `tests/backend/test_final_automation.py`; e2e `frontend/e2e/demo.spec.ts` now uses the automatic request.
