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
