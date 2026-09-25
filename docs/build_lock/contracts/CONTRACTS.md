# Shared contracts — freeze before parallel development

Version `boussla-context-1`. A owns Python/Pydantic definitions. All other lanes consume them. This is the authoritative proposed interface; example JSON is not proof of actual records.

## 1. Scalar conventions

IDs are strings such as `DEMO-C001`; tax identifier fields are display-only synthetic strings, not claims that they pass a real check-digit algorithm. Money is integer millimes with currency `TND` for P0. Quantities and percentages are decimal strings; do not pass binary floats to financial functions. Dates are ISO dates; timestamps include an offset. Use `available_at` as well as `document_date` and `economic_period`.

Null is unknown. Empty collection is “none observed under this query”, not necessarily “none exists”. Enum fields never use unexplained magic numbers. A transaction's invoice, payment and tax views are not summed into one monetary ledger.

## 2. Objects

### Actor and enterprise

```text
Actor(actor_id, role: COMPANY|OFFICER|DEMO_OPERATOR, company_id?, assigned_case_ids[])
Enterprise(company_id, synthetic_mf, display_name, sector, created_on, data_kind=SYNTHETIC)
```

The service resolves scope, not a user-entered MF or LLM response. Demo impersonation mode is local-only and labelled.

### Immutable document

```text
Document(document_id, subject_company_id, case_id, original_filename,
         local_path, sha256, media_type, page_count, received_at,
         uploader_actor_id, acquisition_channel, asserted_issuer_id?,
         origin_group_id, source_record_id?, confidentiality_scope,
         extraction_status, processing_limitations[], supersedes_document_id?)
```

`acquisition_channel`: COMPANY_UPLOAD, OFFICER_UPLOAD, SIMULATED_COUNTERPARTY_REFERENCE, PUBLIC_REFERENCE.

`origin_group_id` is assigned by trusted ingestion logic. A company-uploaded second PDF remains company-supplied regardless of its content or filename. Distinct file hashes do not establish independent origins. Log the source lineage even when the two versions are equivalent.

### Candidate extraction and evidence reference

```text
EvidenceRef(document_id, page?, exact_text?, source_record_id?, field_name?)
CandidateField(field_name, raw_value, normalized_value?, evidence_refs[], ambiguities[])
ExtractionProposal(proposal_id, document_id, candidates[], missing_fields[],
                   mode, model_id?, prompt_version, status)
```

Missing document fields remain null; do not fill them from expected company context and falsely cite the PDF. Exact spans must actually occur in the extracted page. Schema validation does not certify the underlying fact.

### Invoice observations

```text
InvoiceObservation(observation_id, document_id, transaction_id?, perspective,
                   issuer_company_id?, issuer_mf_raw, buyer_company_id?, buyer_mf_raw,
                   invoice_number, invoice_version?, issued_on, available_at,
                   currency, net_millimes, tax_millimes, gross_millimes,
                   referenced_invoice_id?, lines[], transcription_status,
                   origin_group_id)
InvoiceLine(line_id, item_description, normalized_item_code?, quantity,
            unit, unit_price_millimes, line_net_millimes, tax_rate?, project_id?)
```

Perspective: BUYER_RECEIVED, SELLER_ISSUED, INTERNAL_PURCHASE_ENTRY. An internal purchase entry is not a new supplier invoice. Candidate key uses issuer + invoice number + date/version, with ambiguity if necessary. Same invoice number at another supplier is not a duplicate automatically.

### Economic transaction

```text
Transaction(transaction_id, buyer_company_id, seller_company_id?,
            invoice_observation_ids[], project_id?, economic_period,
            source_coverage, correlation_status, canonical_revision)
```

Two observations of one transaction never become two purchases. A copied file is not fraudulent by itself. A duplicate *payment* requires separate settlement evidence.

### Settlements

```text
Payment(payment_id, source_record_id, payer_company_id?, payee_company_id?,
        payer_mapping_ref?, payee_mapping_ref?, currency, amount_millimes,
        status: SETTLED|INITIATED|REVERSED|UNKNOWN, occurred_at, available_at,
        origin_group_id)
PaymentAllocation(payment_id, transaction_id, allocated_millimes, accepted_by, accepted_at)
SettlementAdjustment(adjustment_id, transaction_id, kind, signed_millimes,
                     supporting_refs[], accepted_by?, status)
```

Payment allocations cannot exceed the observed settled amount. Invoice obligations and settlement adjustments must be explicit. Do not treat withholding, financing, fees, advances or part-payments as unexplained fraud. Unsupported mappings/terms produce `INSUFFICIENT_INFORMATION`. P0 uses explicit net payable and settled allocations; adding withholding rules is optional and needs validated semantics.

### Purpose/context

```text
ContextClaim(claim_id, company_id, transaction_id?, project_id?,
             purpose_category, purpose_text, beneficiary_type,
             planned_start?, planned_end?, stage?, reported_stock_qty?,
             author_actor_id, submitted_at, supersedes_claim_id?, evidence_refs[])
Project(project_id, company_id, label, project_type, planned_start?, planned_end?,
        reference_ids[], status)
QuantityReference(reference_id, company_id, project_id, item_code, unit,
                  baseline_kind, quantity, valid_from, valid_to?, source_refs[],
                  acceptance_status, accepted_by?)
Allocation(allocation_id, transaction_id, line_id, target_project_id?,
           target_type: PROJECT|WAREHOUSE|RETURN|OTHER, quantity, unit,
           effective_on, source_refs[], status: PROPOSED|ACCEPTED|REJECTED)
```

Purpose categories: RESALE, OPERATING_USE, LONG_LIVED_ASSET, CONSTRUCTION_PROJECT, OTHER_OR_UNKNOWN. Jev proposes the semantic class; user confirms. Duration is calculated from dates in code. An optional display bucket `<=90 days / >90 days / unknown` is only a configurable demo UI convention, not an accounting/tax classification.

`baseline_kind`: APPROVED_PROCUREMENT_ALLOCATION, CONSUMPTION_ESTIMATE, USER_ESTIMATE. Only a suitable accepted procurement allocation supports the P0 scored quantity comparison. Other kinds support questions/scenarios, not automatic financial-risk points.

### Findings and hypotheses

```text
Finding(finding_id, case_id, company_id, transaction_id, family,
        status: UNRESOLVED|EXPLAINED|INSUFFICIENT|NOT_APPLICABLE,
        severity: decimal-string-or-null, financial_basis?,
        observed_difference_millimes?, quantity_difference?, unit?,
        evidence_refs[], assumption_ids[], missing_evidence_types[],
        calculation_version, case_version)
Hypothesis(hypothesis_id, statement_template_id, supporting_refs[],
           contradicting_refs[], missing_evidence_types[], test_id,
           status: SUPPORTED|CONTRADICTED|UNRESOLVED|NOT_APPLICABLE,
           scope, case_version)
Scenario(scenario_id, label, assumption_ids[], inputs, outputs,
         hypothetical=true, evidence_refs[], changes_canonical_state=false)
```

No `fraud_probability` or automatically generated accusation field. Explanations can coexist. Unknown is not contradiction. Related findings have a shared event/family key for deduplication.

### Scores and views

```text
ScoreSnapshot(company_id, case_version, cutoff, method_id, rules_version,
              review_index: int-or-null, evidence_coverage: number-or-null,
              coverage_complete: bool, contributions[],
              tested_families[], unknown_families[], scope_note,
              unresolved_distinct_transactions, clarification_status)
```

`review_index` is the maximum transaction baseline from the implemented checks. `evidence_coverage` is completed/evaluable known-applicable checks, not probability of truth. Unknown applicability prevents a “complete” claim. Clarification status does not feed the risk index.

### Clarification, evidence acceptance and revision

```text
ClarificationRequest(request_id, case_id, company_id, case_version,
                     fact_ids[], question_ids[], allowed_document_types[],
                     target_response_at?, target_kind=DEMO_SERVICE_TARGET,
                     status: DRAFT|PUBLISHED_IN_DEMO|RESPONDED|EXTENDED|CLOSED,
                     approved_by?, published_at?, available_in_inbox_at?)
ClarificationResponse(response_id, request_id, author_actor_id, claim_ids[],
                      document_ids[], submitted_at)
EvidenceAcceptance(proposal_id, case_id, expected_version, scoped_changes[],
                   actor_id, idempotency_key, reason)
CaseRevision(case_id, version, parent_version?, accepted_evidence_ids[],
             fact_hash, score_snapshot, created_at, reason)
ActionReceipt(idempotency_key, action, case_id, input_hash, resulting_version, result_hash)
```

Officer publication changes the local demo inbox only, not an external channel. Responses are proposals; arrival does not automatically clear a finding. Accept/reject is scoped and revision-bound. No destructive edits to prior claims or documents.

## 3. Service methods (Python contract, not HTTP requirement)

```python
create_case(actor, company_id, project_payload, request_id) -> CaseView
upload_document(actor, case_id, upload_bytes, filename, media_type, expected_version, request_id) -> DocumentView
confirm_transcription(actor, case_id, proposal_id, field_confirmations, expected_version, request_id) -> CaseView
submit_context(actor, case_id, context_payload, expected_version, request_id) -> CaseView
start_analysis(actor, case_id, expected_version) -> AnalysisView
answer_questions(actor, case_id, analysis_id, answers, expected_version, request_id) -> AnalysisView
get_case(actor, case_id) -> CompanyCaseView | OfficerCaseView
list_queue(actor, cutoff, limit, cursor=None) -> QueuePage
prepare_clarification(actor, case_id, expected_version) -> ClarificationDraft
publish_clarification(actor, case_id, draft_id, expected_version, request_id) -> RequestView
submit_response(actor, case_id, request_id, payload, expected_version, idempotency_key) -> ResponseView
accept_evidence(actor, case_id, proposal_id, expected_version, idempotency_key) -> RevisionResult
reject_evidence(actor, case_id, proposal_id, expected_version, reason, idempotency_key) -> RevisionResult
get_history(actor, case_id) -> HistoryView
export_dossier(actor, case_id, audience, expected_version) -> LocalDraftArtifact
```

A supplies a service fake with this shape by minute 30. B/C implementations plug into named functions; D must not implement financial logic inside UI pages.

## 4. Errors

`FORBIDDEN`, `CROSS_COMPANY`, `STALE_REVISION`, `IDEMPOTENCY_CONFLICT`, `UNSUPPORTED_FILE`, `LIMIT_EXCEEDED`, `UNSUPPORTED_LAYOUT`, `UNKNOWN_IDENTITY_MAPPING`, `INCOMPATIBLE_BASIS`, `INCOMPATIBLE_UNIT`, `INSUFFICIENT_INFORMATION`, `ALLOCATION_OVERFLOW`, `DUPLICATE_ACCEPTANCE`, `MODEL_UNAVAILABLE`, `RETRIEVAL_UNAVAILABLE`, `INVALID_EVIDENCE_REFERENCE`.

A provider failure is not a financial discrepancy. A manual fallback cannot bypass an authorization or allocation failure.

## 5. Audience scoping

Company: own uploaded/received records, own purpose claims, approved neutral questions, own responses and allowed review feedback. Officer: assigned cases, evidence-scoped internal findings. Neither a company nor an LLM may request another company's internal tax status by supplying its identifier.

The service constructs distinct evidence bundles before retrieval/model calls. A taxpayer-facing prompt must never receive internal ranking or unrelated counterpart documents and simply be told “don't reveal this.” Every output reference is checked against the bundle.
