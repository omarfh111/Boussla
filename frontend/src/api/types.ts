/** Local role simulation headers (the server maps each to one roster actor). */
export type Role = "COMPANY" | "OFFICER" | "OPERATOR";
export type Mode =
  "LIVE" | "CACHED" | "MANUAL" | "TEMPLATE" | "NOT_RUN" | "ERROR" | "MOCK";
export interface Bootstrap {
  role: "COMPANY" | "OFFICER" | "DEMO_OPERATOR";
  case_ids: string[];
  banner_fr: string;
  demo_admin?: DemoAdminCapabilities;
}
export interface DemoAdminCapabilities {
  can_list: boolean;
  can_seed: boolean;
  can_reset: boolean;
  can_add: boolean;
  can_delete: boolean;
}
/** Mirrors boussla.contracts.EnterpriseProfileView (officer only, synthetic). */
export interface EnterpriseProfile {
  company_id: string;
  display_name: string;
  synthetic_identifier: string;
  sector: string;
  created_on: string;
  activity_start: string | null;
  activity_end: string | null;
  portfolio_member: boolean;
  data_kind: "SYNTHETIC";
}
export interface PaymentTimelineEntry {
  payment_id: string;
  transaction_id: string | null;
  occurred_at: string;
  amount_millimes: number;
  currency: string;
  status: string;
  origin_group_id: string;
}
export interface MonthlyActivityEntry {
  month: string;
  transaction_count: number;
  invoice_observation_count: number;
  settled_outflow_millimes: number;
  source_label: string;
  coverage_status: "COVERED" | "UNKNOWN";
  coverage_source_id: string | null;
}
/** Lane B synthetic authorized snapshot: context only, no bank access, no proof. */
export interface FinancialSnapshot {
  label_fr: string;
  data_kind: "SYNTHETIC";
  as_of: string;
  currency: string;
  observed_outflows_millimes: number;
  observed_settlements_millimes: number;
  documented_payable_millimes: number;
  outstanding_documented_payable_millimes: number;
  inflows_millimes: null;
  scope: string;
  statement_fr: string;
  source_count: number;
}
/** Lane B neutral history observation (review context, never a finding). */
export interface HistorySignal {
  signal_id: string;
  company_id: string;
  reason_code: string;
  period: string;
  metric: string;
  observed_value: string;
  baseline_value: string | null;
  baseline_periods: string[];
  evidence_source_ids: string[];
  explanation_fr: string;
  method: string;
  mode: Mode;
  affects_review_index: false;
}
export interface HistoricalFactor {
  reason_code: string;
  contribution: number;
  source_signal_ids: string[];
  explanation_fr: string;
}
export interface OperationalConfidenceFactor {
  code: string;
  numerator: number;
  denominator: number;
  nominal_weight: number;
  effective_weight: string;
  weighted_contribution: string;
  reason_codes: string[];
  source_ids: string[];
  explanation_fr: string;
}
/** Server-computed queue urgency; React never derives it. */
export interface TriageAssessment {
  triage_priority: number;
  review_index: number | null;
  reason_codes: string[];
  components: Record<string, number>;
  formula_version: string;
  note_fr: string;
  not_fraud_probability: true;
}
export interface ClarificationDeadline {
  request_id: string;
  origin: "OFFICER" | "AUTOMATIC";
  status: string;
  target_response_at: string | null;
  target_kind: string;
  overdue: boolean;
  overdue_days: number;
  note_fr: string;
}
export interface AdminEnterprise {
  company_id: string;
  display_name: string;
  sector: string;
  synthetic_identifier: string;
  case_id: string;
  case_version: number | null;
  transaction_count: number;
  data_kind: "SYNTHETIC";
}
export interface AdminResult {
  action: "SEED" | "RESET" | "ADD" | "DELETE";
  enterprise_count: number;
  case_ids: string[];
  notice_fr: string;
}
export interface DocumentView {
  processing_status?: string;
  analysis?: {
    calculated_at: string;
    rule_version: string;
    classification: string;
    authenticity_statement: string;
    confidence?: {
      value: number | null;
      level: string;
      measured_dimensions: number;
      rule_version: string;
      explanation_fr: string;
      factors: { code: string; value: number | null; explanation_fr: string }[];
    } | null;
    linked_cause_ids: string[];
    proposed_action: string;
    stages: { code: string; status: string; explanation_fr: string }[];
    checks: {
      code: string;
      status: string;
      explanation_fr: string;
      source_ids: string[];
    }[];
    limitations: string[];
  } | null;
  document: {
    document_id: string;
    original_filename: string;
    sha256: string;
    page_count: number | null;
    acquisition_channel: string;
    origin_group_id?: string | null;
    received_at: string;
    extraction_status: string;
    processing_limitations: string[];
  };
  routing: { candidate_class: string; mode: Mode } | null;
  extraction: {
    proposal_id?: string;
    mode: Mode;
    status: string;
    candidates?: {
      field_name: string;
      raw_value: string | null;
      normalized_value: string | null;
      ambiguities: string[];
    }[];
  } | null;
  integrity: { signature_status: string; limitations: string[] } | null;
  mode: Mode;
}
export interface TransactionSummary {
  transaction_id: string;
  counterparty_display_name: string | null;
  counterparty_company_id?: string | null;
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
  project_id?: string | null;
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
  scope_note_fr?: string | null;
  related_fact_ids?: string[];
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
    origin?: "AUTOMATIC" | "OFFICER";
    reason_codes?: string[];
    reason_text_fr?: string | null;
    target_response_at?: string | null;
    target_kind?: string;
    /** Read-time follow-up state computed by the service. */
    overdue_state?: "ON_TRACK" | "FOLLOW_UP_DUE" | null;
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
  audience: "COMPANY" | "OFFICER";
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
  capabilities?: { supports_null_project_id: boolean };
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
  transaction_id?: string;
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
  inputs: Record<string, string>;
  outputs: Record<string, string>;
  hypothetical: true;
}
/** One fixed-catalogue candidate explanation. Status is a label, never a probability. */
export interface BriefHypothesis {
  hypothesis_id: string;
  name_fr: string;
  status: "SUPPORTED" | "PLAUSIBLE" | "WEAK" | "CONTRADICTED" | "INSUFFICIENT";
  supporting_refs: string[];
  contradicting_refs: string[];
  missing_evidence: string[];
  why_it_matters_fr: string;
}
/** Mirrors boussla.contracts.InvestigatorBriefView (officer only). */
export interface InvestigatorBrief {
  case_id: string;
  case_version: number;
  summary_fr: string;
  key_observations: { kind: string; text_fr: string; source_codes: string[] }[];
  top_hypotheses: BriefHypothesis[];
  missing_information: string[];
  changes_since_previous_version: string[];
  questions_proposed: string[];
  questions_already_asked: string[];
  reference_rule_ids: string[];
  history_signal_codes: string[];
  limitations: string[];
  mode: Mode;
  authoritative: false;
  label_fr: string;
  disclaimer_fr: string;
}
export interface InvoiceObservation {
  observation_id: string;
  document_id: string;
  transaction_id: string | null;
  perspective: string;
  issuer_company_id: string | null;
  buyer_company_id: string | null;
  invoice_number: string;
  invoice_version: string | null;
  issued_on: string;
  currency: string;
  net_millimes: number;
  tax_millimes: number;
  gross_millimes: number;
  origin_group_id: string;
  lines: {
    line_id: string;
    item_description: string | null;
    quantity: string;
    unit: string;
    unit_price_millimes: number;
    line_net_millimes: number;
  }[];
}
/** Pair-scoped buyer/seller comparison computed by the service. */
export interface InvoiceComparison {
  transaction_id: string;
  buyer_observation_id: string | null;
  seller_observation_id: string | null;
  status: "CONCORDANT" | "DIFFERENCES" | "SINGLE_OBSERVATION" | "AMBIGUOUS";
  reconciliation_status?: string;
  candidate_observation_ids?: string[];
  payment_ids?: string[];
  delivery_ids?: string[];
  project_ids?: string[];
  rule_version?: string;
  calculated_at?: string | null;
  label_fr: string;
  difference_fields: string[];
  counterparty_reason_code: string | null;
}
export interface ScoreSnapshot {
  calculated_at?: string | null;
  engine_version?: string;
  cause_ids?: string[];
  review_index: number | null;
  raw_review_index: number | null;
  decisive_transaction_id: string | null;
  cause_progress: CauseProgress[];
  evidence_coverage: string | null;
  clarification_status: string;
  scope_note: string;
  rules_version: string;
  coverage_complete: boolean;
}
export interface CauseProgress {
  cause_id?: string;
  initial_weight?: string | null;
  evidence_ids?: string[];
  explanation_ids?: string[];
  resolved_by?: string | null;
  resolved_at?: string | null;
  rule_version?: string;
  transaction_id: string;
  family: "COUNTERPARTY" | "SETTLEMENT" | "QUANTITY";
  raw_contribution: string;
  current_contribution: string;
  stage:
    | "UNRESOLVED"
    | "EXPLANATION_RECEIVED"
    | "EVIDENCE_RECEIVED"
    | "EVIDENCE_COHERENT"
    | "RESOLVED";
  provisional: boolean;
  reason_code: string | null;
  source_ids: string[];
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
export interface CaseIndicator {
  value: string | null;
  status: string;
  factors: {
    code: string;
    value: string | null;
    contribution: string | null;
    source_ids: string[];
    explanation: string;
  }[];
  explanation: string;
  calculated_at: string;
  rule_version: string;
  sample_size: number;
}
export interface BehaviorProfile {
  as_of: string;
  observed_period: string;
  baseline_periods: string[];
  rule_version: string;
  signals?: {
    code: "RESPONSE_DELAY_DEVIATION" | "MONTHLY_AMOUNT_DEVIATION";
    metric_code: string;
    currency: string | null;
    observed_value: string;
    baseline_value: string;
    ratio: string;
    data_quality: "AVAILABLE" | "LIMITED_DATA";
    baseline_months: number;
    current_sample_size: number;
    source_ids: string[];
    explanation_fr: string;
    rule_version: string;
  }[];
  metrics: {
    code: string;
    label_fr: string;
    current_value: string | null;
    baseline_value: string | null;
    change_percent: string | null;
    status: string;
    unit: string;
    currency: string | null;
    sample_size: number;
    source_ids: string[];
    explanation_fr: string;
  }[];
}
export interface RecommendedAction {
  action_id: string;
  kind: string;
  title_fr: string;
  priority: number;
  reason: string;
  source_causes: string[];
  required_documents: string[];
  status: "OPEN" | "WAITING" | "COMPLETED";
  source_ids: string[];
  rule_version: string;
}
export interface ResolutionImpact {
  step: number;
  cause_id: string;
  family: "COUNTERPARTY" | "SETTLEMENT" | "QUANTITY";
  transaction_id: string;
  before_index: number;
  after_index: number;
  source_ids: string[];
  case_version: number;
  calculated_at: string | null;
  rule_version: string;
  hypothetical: true;
}
export interface OfficerCaseView extends BaseCase {
  impact_if_resolved?: ResolutionImpact[];
  recommended_actions?: RecommendedAction[];
  behavior_profile?: BehaviorProfile | null;
  indicators?: Record<string, CaseIndicator>;
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
  invoice_observations: InvoiceObservation[];
  invoice_comparisons: InvoiceComparison[];
  investigator_brief: InvestigatorBrief | null;
  triage: TriageAssessment | null;
  clarification_deadlines: ClarificationDeadline[];
  history_signals: HistorySignal[];
  history_signal_index: number | null;
  history_signal_status: "INSUFFICIENT_DATA" | "AVAILABLE";
  history_signal_factors: HistoricalFactor[];
  history_signal_method: string | null;
  operational_confidence_index: number | null;
  operational_confidence_status: "INSUFFICIENT_DATA" | "AVAILABLE";
  operational_confidence_as_of: string | null;
  operational_confidence_factors: OperationalConfidenceFactor[];
  operational_confidence_eligible_observations: number;
  operational_confidence_method: string;
  operational_confidence_sample_size?: number;
  operational_confidence_data_quality?: string;
  operational_confidence_sample_note_fr?: string;
  operational_confidence_window_start?: string | null;
  enterprise_profile: EnterpriseProfile | null;
  monthly_activity: MonthlyActivityEntry[];
  payment_timeline: PaymentTimelineEntry[];
  financial_snapshot: FinancialSnapshot | null;
  quantity_references: {
    reference_id: string;
    quantity: string;
    unit: string;
    project_id: string;
  }[];
}
export interface QueueItem {
  case_id: string;
  company_id: string;
  company_display_name: string;
  case_version: number;
  review_index: number | null;
  evidence_coverage: string | null;
  coverage_complete: boolean;
  active_finding_count: number;
  clarification_status: string;
  scope_note: string;
  /** Queue urgency computed by the service (0..100); never the review index. */
  triage_priority: number | null;
  triage_reason_codes: string[];
  sector: string | null;
  synthetic_identifier: string | null;
  last_activity_at: string | null;
  history_signal_codes: string[];
  history_anomaly: boolean | null;
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
export interface InvestigationAnswer {
  case_id: string;
  case_version: number;
  question: string;
  answer_fr: string;
  citations: {
    source_id: string;
    kind: string;
    label_fr: string;
    source_url: string | null;
  }[];
  calculated_at: string;
  rule_version: string;
  mode: "TEMPLATE";
  authoritative: false;
  limitations: string[];
}
export interface NetworkView {
  scope: "ALL" | "COMPANY" | "CASE";
  scope_id: string | null;
  calculated_at: string;
  rule_version: string;
  note_fr: string;
  nodes: {
    node_id: string;
    kind: string;
    label: string;
    case_ids: string[];
    attributes: Record<string, string>;
  }[];
  edges: {
    edge_id: string;
    source: string;
    target: string;
    kind: string;
    case_id: string;
    source_ids: string[];
    provenance_status: string;
  }[];
}
export interface NotificationFeedView {
  case_id: string;
  audience: "COMPANY" | "OFFICER";
  items: {
    notification_id: string;
    kind: string;
    title_fr: string;
    message_fr: string;
    occurred_at: string;
    case_version: number;
    source_event_id: string | null;
    status: "RECORDED";
  }[];
}
export interface AuditView {
  case_id: string;
  legacy_events_without_audit: number;
  records: {
    audit_id: string;
    event_id: string;
    actor_id: string;
    at: string;
    case_version: number;
    action: string;
    reason: string;
    before: {
      review_index: number | null;
      cause_contributions: Record<string, string>;
      calculated_at: string | null;
    } | null;
    after: {
      review_index: number | null;
      cause_contributions: Record<string, string>;
      calculated_at: string | null;
    } | null;
    evidence_ids: string[];
    rules_version: string | null;
    engine_version: string | null;
  }[];
}

export interface HistoryView {
  revisions: {
    version: number;
    parent_version: number | null;
    reason: string;
    created_at: string;
    score_snapshot?: ScoreSnapshot | null;
  }[];
  events: {
    event_id: string;
    kind: string;
    summary: string;
    case_version: number;
    at: string;
    actor_id?: string;
    fact_ids?: string[];
  }[];
  operational_confidence_changes?: {
    from_version: number;
    to_version: number;
    as_of: string;
    before_index: number | null;
    after_index: number | null;
    factor_deltas: {
      code: string;
      before_contribution: string | null;
      after_contribution: string | null;
      before_numerator: number | null;
      before_denominator: number | null;
      after_numerator: number | null;
      after_denominator: number | null;
      source_ids: string[];
      reason_codes: string[];
    }[];
  }[];
}
export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}
