# Final portfolio UI — integrated contract

Integrated on `integration/final-release`. The Python service is authoritative for scores, triage, findings, permissions, revisions and synthetic provenance; React renders server values only and never computes an index, a triage value or an overdue state. Types in `src/api/types.ts` mirror `boussla/contracts.py` (`boussla-automation-1`).

| Screen | Backend source | Notes |
| --- | --- | --- |
| Portfolio (officer queue) | `GET /api/officer/queue?cursor=` → `QueueItem` | `triage_priority`, `triage_reason_codes`, `review_index`, `sector`, `synthetic_identifier`, `last_activity_at`, `history_signal_codes`, `history_anomaly`. Default order = server order (triage desc, review index desc, last activity, case ID). Search/filter/sort act on loaded rows only. |
| Enterprise 360 | `OfficerCaseView` | `enterprise_profile`, `monthly_activity`, `payment_timeline`, `financial_snapshot` (lane B, labelled « Instantané financier synthétique — source autorisée simulée »), `history_signals` (lane B codes), `context_claims`, revisions from `/history`. |
| Buyer / seller comparison | `OfficerCaseView.invoice_comparisons` | Pair-scoped by transaction ID; only server `difference_fields` are highlighted; concordance is labelled « Observations concordantes ». |
| Automatic request | `RequestView.request` | `origin`, `reason_codes`, `reason_text_fr`, `target_response_at`, `target_kind`, read-time `overdue_state` (`FOLLOW_UP_DUE` → « Relance à prévoir »). |
| Investigator + top hypotheses | `OfficerCaseView.investigator_brief` (`InvestigatorBriefView`) | Lane C catalogue only, max 5 hypotheses; support status is a label, never a probability. |
| Scenarios | `OfficerCaseView.scenarios` | `outputs.hypothetical_review_index` only when the deterministic checks computed it on a cloned fact set. |
| No-project context | `CompanyCaseView.capabilities.supports_null_project_id` | Sends `project_id: null`. |
| Demo administration | `/api/admin/*` with `X-Boussla-Demo-Role: OPERATOR` | DEMO_OPERATOR only; list, seed, reset (confirm `RESET`), add, delete (confirm = company ID). |

Role switching remains a local simulation. The company view never receives the officer queue, triage, findings, investigator brief, history signals or administration data.
