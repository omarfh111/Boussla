# Final portfolio UI contract handoff

This branch starts at main `b33ae94f37e09c7cf5aa76054d114176a843249a`. It changes only the React consumer. The current API remains authoritative for scores, findings, permissions, revisions, and synthetic provenance. Fields below are optional in `src/api/types.ts`; an absent field is displayed as unavailable, never inferred.

## Current read paths

- `GET /api/demo/bootstrap` supplies role and assigned case IDs. The UI checks an opened portfolio case against these IDs; the server must continue to enforce authorization.
- `GET /api/officer/queue?cursor=...` supplies paged case rows. Search, sorting, and filtering act on loaded rows; the UI has a “load more” action when `next_cursor` is present.
- `GET /api/cases/{case_id}` supplies distinct company/officer views.
- `GET /api/cases/{case_id}/history` supplies the revision timeline.

## Additive fields expected for final integration

| Owner | Response | Fields consumed | UI behavior until supplied |
| --- | --- | --- | --- |
| A/B | Officer queue item | `company_id`, `sector`, `synthetic_identifier`, `triage: { label_fr, level, rank }`, `coverage_complete`, `last_activity_at`, `historical_signals`, `history_anomaly` | Unknown cells are labelled “Non communiqué”; triage, evidence-completeness, history, and sector filters are disabled when unavailable. Triage is never derived from `review_index`. |
| A | Officer case | `enterprise_profile`, `payment_timeline`, `monthly_activity`, `financial_activity` | Enterprise 360 uses current case transactions, context claims, and history; missing enterprise-wide data remains empty. Current observed settlement amounts are shown per transaction without summing them. |
| A/B | Officer case | `invoice_comparison: { status, reason_code, difference_fields }` | Buyer/seller observations are grouped by trusted `transaction_id` if present, otherwise issuer, invoice number, and date. The UI highlights only backend-supplied `difference_fields`, and only when one pair is present. Multiple-pair findings require a pair-scoped comparison contract. |
| A | Clarification request | `origin`, `reason_text_fr` or `reason_codes`, `target_response_at`, `target_kind`, `overdue_state` | The automatic-request banner appears only for `origin: "AUTOMATIC"`. Target dates and overdue state are displayed only when returned by the service. The UI does not calculate overdue status or publish requests automatically. |
| C with A | Officer case | `investigator_brief: InvestigatorBrief` | The seven-section investigator panel has a clear unavailable state. It never fabricates a summary, evidence, questions, or public references. |
| B with A | Officer case | Hypothesis `name_fr`, `support_index`, `supporting_refs`, `contradicting_refs`; scenario `outputs.review_index` or `outputs.hypothetical_review_index` when supported | Hypothesis cards show at most five; scenario cards display only service outputs. `support_index` is labelled “Support de l’hypothèse”. |
| A | Company case | `capabilities.supports_null_project_id` | The “Aucun projet / usage général de l’entreprise” option is hidden until the capability is true. Only then does the context form send `project_id: null`. |
| A | Authorized demo operator API | Separate list/seed/reset/add/delete endpoints and role-scoped capability contract | All administration actions stay disabled. The visible list currently comes from the first page of assigned queue cases, not an enterprise registry. |

The current `invoice_comparison` shape is case-level. For a portfolio enterprise with several transactions, A/B should provide comparison objects keyed by transaction or observation IDs before the UI highlights differences across multiple pairs. Enterprise 360 likewise needs an authorized enterprise-level history contract to cover cases beyond the selected case.

Role switching is a local simulation. The company view never receives `InvestigatorBrief`, officer queue, triage, internal findings, or demo administration data. Production identity and permissions remain an A integration task.
