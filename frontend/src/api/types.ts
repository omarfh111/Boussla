export type Role = "COMPANY" | "OFFICER";
export type Mode =
  "LIVE" | "CACHED" | "MANUAL" | "TEMPLATE" | "NOT_RUN" | "ERROR" | "MOCK";
export interface Bootstrap {
  role: Role;
  case_ids: string[];
  banner_fr: string;
}
export interface DocumentView {
  document: {
    document_id: string;
    original_filename: string;
    sha256: string;
    page_count: number | null;
    acquisition_channel: string;
    received_at: string;
    extraction_status: string;
    processing_limitations: string[];
  };
  routing: { candidate_class: string; mode: Mode } | null;
  extraction: { mode: Mode; status: string } | null;
  integrity: { signature_status: string; limitations: string[] } | null;
  mode: Mode;
}
export interface TransactionSummary {
  transaction_id: string;
  counterparty_display_name: string | null;
  invoice_number: string | null;
  issued_on: string | null;
  invoiced_gross_millimes: number | null;
  settled_millimes: number | null;
  declared_millimes: number | null;
  corroboration_status: string;
  project_id: string | null;
}
export interface Allocation {
  allocation_id: string;
  transaction_id: string;
  line_id: string;
  target_project_id: string | null;
  quantity: string;
  unit: string;
  status: string;
}
export type Horizon = "SHORT_HORIZON" | "LONGER_HORIZON" | "UNKNOWN";
export interface ContextClaim {
  claim_id: string;
  purpose_category: string;
  purpose_text: string;
  beneficiary_type: string;
  planned_start: string | null;
  planned_end: string | null;
  stage: string | null;
  submitted_at: string;
  declared_horizon: Horizon;
  supersedes_claim_id: string | null;
}
/** Mirrors boussla.contracts.ContextAssessmentView (clarification aid, never a score). */
export interface ContextAssessmentView {
  claim_id: string;
  declared_horizon: Horizon;
  interpreted_horizon: Horizon;
  calculated_horizon: Horizon;
  declared_purpose_category: string;
  interpreted_purpose_category: string;
  duration_days: number | null;
  consistency_status: "CONSISTENT" | "NEEDS_CLARIFICATION" | "INSUFFICIENT";
  reason_codes: string[];
  recommended_question_ids: string[];
  supporting_spans: string[];
  corroboration_status: "NOT_ASSESSED";
  interpretation_mode: Mode;
  horizon_convention_fr: string;
}
export interface Question {
  question_id: string;
  text_fr: string;
  answer_kind: string;
  choices: string[];
}
export interface RequestView {
  request: {
    request_id: string;
    status: string;
    published_at: string | null;
    allowed_document_types: string[];
  };
  questions: Question[];
  text_fr: string;
  mode: Mode;
}
export interface ResponseView {
  response: {
    response_id: string;
    request_id: string;
    document_ids: string[];
    answers: Record<string, string>;
  };
  proposal_ids: string[];
  case_version: number;
}
export interface BaseCase {
  audience: Role;
  case_id: string;
  company_id: string;
  company_display_name: string;
  case_version: number;
  documents: DocumentView[];
  transactions: TransactionSummary[];
  projects: { project_id: string; label: string }[];
  context_claims: ContextClaim[];
  allocations: Allocation[];
  context_assessment: ContextAssessmentView | null;
  mode: Mode;
  banner_fr: string;
}
export interface CompanyCaseView extends BaseCase {
  audience: "COMPANY";
  open_questions: Question[];
  inbox: RequestView[];
  responses: ResponseView["response"][];
}
export interface EvidenceRef {
  document_id: string | null;
  source_record_id: string | null;
  page: number | null;
}
export interface Finding {
  finding_id: string;
  family: string;
  status: string;
  reason_code: string | null;
  quantity_difference: string | null;
  unit: string | null;
  calculation_version: string;
  evidence_refs: EvidenceRef[];
  missing_evidence_types: string[];
}
export interface Hypothesis {
  hypothesis_id: string;
  status: string;
  scope: string;
  missing_evidence_types: string[];
}
export interface Scenario {
  scenario_id: string;
  label: string;
  outputs: Record<string, unknown>;
}
export interface ScoreSnapshot {
  review_index: number | null;
  evidence_coverage: string | null;
  clarification_status: string;
  scope_note: string;
  rules_version: string;
  coverage_complete: boolean;
}
export interface EvidenceProposal {
  proposal_id: string;
  status: string;
  source_document_id: string | null;
  transaction_id: string;
  line_id: string;
  unit: string;
  changes: {
    action: string;
    allocation_id: string;
    target_project_id: string | null;
    old_quantity: string | null;
    new_quantity: string;
  }[];
}
export interface RetrievedPassage {
  rule_id: string;
  document_title: string;
  text: string;
  source_url: string;
  page: number | null;
  article: string | null;
  mode: Mode;
}
export interface GroundedNoteView {
  summary_fr: string;
  candidate_rule_ids: string[];
  applicability_questions: string[];
  limitations: string[];
  provider_model: string | null;
  generation_mode: Mode;
  disclaimer_fr: string;
}
export interface OfficerCaseView extends BaseCase {
  audience: "OFFICER";
  score: ScoreSnapshot | null;
  findings: Finding[];
  hypotheses: Hypothesis[];
  scenarios: Scenario[];
  requests: RequestView[];
  responses: ResponseView["response"][];
  proposals: EvidenceProposal[];
  candidate_passages: RetrievedPassage[];
  reference_note: GroundedNoteView | null;
  mode_by_node: Record<string, Mode>;
  invoice_observations: {
    document_id: string;
    perspective: string;
    issuer_company_id: string | null;
    buyer_company_id: string | null;
    invoice_number: string;
    issued_on: string;
    gross_millimes: number;
    origin_group_id: string;
    lines: { line_id: string; quantity: string; unit: string }[];
  }[];
  quantity_references: {
    reference_id: string;
    quantity: string;
    unit: string;
    project_id: string;
  }[];
}
export interface QueueItem {
  case_id: string;
  company_display_name: string;
  case_version: number;
  review_index: number | null;
  evidence_coverage: string | null;
  active_finding_count: number;
  clarification_status: string;
  scope_note: string;
}
export interface QueuePage {
  items: QueueItem[];
  next_cursor: string | null;
  mode: Mode;
}
export interface ClarificationDraft {
  draft_id: string;
  questions: Question[];
  text_fr: string;
  allowed_document_types: string[];
  case_version: number;
}
export interface RevisionResult {
  outcome: "ACCEPTED" | "REJECTED";
  previous_version: number;
  new_version: number;
  allocations_before: Allocation[];
  allocations_after: Allocation[];
  findings_before: Finding[];
  findings_after: Finding[];
  score_before: ScoreSnapshot | null;
  score_after: ScoreSnapshot | null;
  replayed: boolean;
}
export interface HistoryView {
  revisions: {
    version: number;
    parent_version: number | null;
    reason: string;
    created_at: string;
  }[];
  events: {
    event_id: string;
    kind: string;
    summary: string;
    case_version: number;
    at: string;
  }[];
}
export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}
