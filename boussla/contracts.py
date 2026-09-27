"""Shared typed contracts — lane A owns this file.

Python source of truth for `docs/build_lock/contracts/CONTRACTS.md`
(version `boussla-automation-1`). B, C and D import from here; propose changes
through `docs/build_lock/handoffs/CHANGE_REQUESTS.md`, never fork a copy.

Conventions (CONTRACTS.md §1):
- money is integer millimes (``Millimes``), currency ``TND`` for P0;
- quantities/percentages are decimal strings (``DecimalStr``), never floats;
- ``None`` means unknown; an empty list means "none observed under this query";
- all models are immutable and reject unknown fields.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Annotated, Literal, Protocol, runtime_checkable

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StrictInt

from boussla import CONTRACT_VERSION  # noqa: F401  re-exported for consumers


# ---------------------------------------------------------------------------
# Scalars
# ---------------------------------------------------------------------------

def _check_decimal(value: str) -> str:
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"not a decimal string: {value!r}") from exc
    if not parsed.is_finite():
        raise ValueError("non-finite decimal")
    return value


def _check_non_negative(value: int) -> int:
    if value < 0:
        raise ValueError("millimes must be non-negative")
    return value


DecimalStr = Annotated[str, Field(strict=True), AfterValidator(_check_decimal)]
"""Decimal as a string, e.g. ``"2000"`` or ``"0.19"``. Floats are rejected."""

Millimes = StrictInt
"""Signed integer millimes (1 TND = 1000 millimes). Booleans/floats rejected."""

NonNegMillimes = Annotated[StrictInt, AfterValidator(_check_non_negative)]

Currency = Literal["TND"]


class Contract(BaseModel):
    """Base for all shared objects: immutable, strict about unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=False)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Role(str, Enum):
    COMPANY = "COMPANY"
    OFFICER = "OFFICER"
    DEMO_OPERATOR = "DEMO_OPERATOR"


class Audience(str, Enum):
    COMPANY = "COMPANY"
    OFFICER = "OFFICER"


class Mode(str, Enum):
    """Provenance of a node/view result. MOCK marks lane A's service fake."""

    LIVE = "LIVE"
    CACHED = "CACHED"
    MANUAL = "MANUAL"
    TEMPLATE = "TEMPLATE"
    NOT_RUN = "NOT_RUN"
    ERROR = "ERROR"
    MOCK = "MOCK"


class ErrorCode(str, Enum):
    FORBIDDEN = "FORBIDDEN"
    CROSS_COMPANY = "CROSS_COMPANY"
    STALE_REVISION = "STALE_REVISION"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    UNSUPPORTED_FILE = "UNSUPPORTED_FILE"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    UNSUPPORTED_LAYOUT = "UNSUPPORTED_LAYOUT"
    UNKNOWN_IDENTITY_MAPPING = "UNKNOWN_IDENTITY_MAPPING"
    INCOMPATIBLE_BASIS = "INCOMPATIBLE_BASIS"
    INCOMPATIBLE_UNIT = "INCOMPATIBLE_UNIT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    ALLOCATION_OVERFLOW = "ALLOCATION_OVERFLOW"
    DUPLICATE_ACCEPTANCE = "DUPLICATE_ACCEPTANCE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    RETRIEVAL_UNAVAILABLE = "RETRIEVAL_UNAVAILABLE"
    INVALID_EVIDENCE_REFERENCE = "INVALID_EVIDENCE_REFERENCE"
    NOT_FOUND = "NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    INVALID_INPUT = "INVALID_INPUT"
    """Malformed request structure, e.g. a property outside the input contract."""


class AcquisitionChannel(str, Enum):
    COMPANY_UPLOAD = "COMPANY_UPLOAD"
    OFFICER_UPLOAD = "OFFICER_UPLOAD"
    SIMULATED_COUNTERPARTY_REFERENCE = "SIMULATED_COUNTERPARTY_REFERENCE"
    PUBLIC_REFERENCE = "PUBLIC_REFERENCE"


class Perspective(str, Enum):
    BUYER_RECEIVED = "BUYER_RECEIVED"
    SELLER_ISSUED = "SELLER_ISSUED"
    INTERNAL_PURCHASE_ENTRY = "INTERNAL_PURCHASE_ENTRY"


class PaymentStatus(str, Enum):
    SETTLED = "SETTLED"
    INITIATED = "INITIATED"
    REVERSED = "REVERSED"
    UNKNOWN = "UNKNOWN"


class PurposeCategory(str, Enum):
    RESALE = "RESALE"
    OPERATING_USE = "OPERATING_USE"
    LONG_LIVED_ASSET = "LONG_LIVED_ASSET"
    CONSTRUCTION_PROJECT = "CONSTRUCTION_PROJECT"
    OTHER_OR_UNKNOWN = "OTHER_OR_UNKNOWN"


class HorizonBucket(str, Enum):
    """Project horizon bucket. BOUSSLA demo convention (0–90 days = short, 91+ = longer),
    not a legal, tax, accounting, risk or fraud classification. Shared by the context
    layer (boussla.context) and ContextClaim; never an input to scoring."""

    SHORT_HORIZON = "SHORT_HORIZON"
    LONGER_HORIZON = "LONGER_HORIZON"
    UNKNOWN = "UNKNOWN"


class BaselineKind(str, Enum):
    APPROVED_PROCUREMENT_ALLOCATION = "APPROVED_PROCUREMENT_ALLOCATION"
    CONSUMPTION_ESTIMATE = "CONSUMPTION_ESTIMATE"
    USER_ESTIMATE = "USER_ESTIMATE"


class AllocationTarget(str, Enum):
    PROJECT = "PROJECT"
    WAREHOUSE = "WAREHOUSE"
    RETURN = "RETURN"
    OTHER = "OTHER"


class AllocationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class FindingFamily(str, Enum):
    COUNTERPARTY = "COUNTERPARTY"
    SETTLEMENT = "SETTLEMENT"
    QUANTITY = "QUANTITY"


class FindingStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    EXPLAINED = "EXPLAINED"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ProgressStage(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    EXPLANATION_RECEIVED = "EXPLANATION_RECEIVED"
    EVIDENCE_RECEIVED = "EVIDENCE_RECEIVED"
    EVIDENCE_COHERENT = "EVIDENCE_COHERENT"
    RESOLVED = "RESOLVED"


class HypothesisStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RequestStatus(str, Enum):
    DRAFT = "DRAFT"
    PUBLISHED_IN_DEMO = "PUBLISHED_IN_DEMO"
    RESPONDED = "RESPONDED"
    EXTENDED = "EXTENDED"
    CLOSED = "CLOSED"


class ClarificationStatus(str, Enum):
    """Administrative status only; never feeds the review index."""

    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    EXTENSION_REQUESTED = "EXTENSION_REQUESTED"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    FOLLOW_UP_STATUS_UNKNOWN = "FOLLOW_UP_STATUS_UNKNOWN"
    CLOSED = "CLOSED"


class ProposalStatus(str, Enum):
    AWAITING_HUMAN_REVIEW = "AWAITING_HUMAN_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class AnalysisStatus(str, Enum):
    COMPLETED = "COMPLETED"
    AWAITING_COMPANY_ANSWER = "AWAITING_COMPANY_ANSWER"
    NEEDS_OFFICER_REVIEW = "NEEDS_OFFICER_REVIEW"
    ERROR = "ERROR"


class DocumentClass(str, Enum):
    """Jev routing categories (config/prompt_templates.md). Always keep OTHER_OR_UNKNOWN."""

    INVOICE = "INVOICE"
    PAYMENT_RECORD = "PAYMENT_RECORD"
    ALLOCATION_REFERENCE = "ALLOCATION_REFERENCE"
    ALLOCATION_RESPONSE = "ALLOCATION_RESPONSE"
    DELIVERY_RECORD = "DELIVERY_RECORD"
    CREDIT_NOTE = "CREDIT_NOTE"
    OTHER_OR_UNKNOWN = "OTHER_OR_UNKNOWN"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BousslaError(Exception):
    """Typed service error. ``code`` is the contract enum; message is safe to show."""

    def __init__(self, code: ErrorCode, message: str = "", **details: object) -> None:
        self.code = code
        self.message = message or code.value
        self.details = details
        super().__init__(f"{code.value}: {self.message}")


# ---------------------------------------------------------------------------
# Actor and enterprise
# ---------------------------------------------------------------------------

class Actor(Contract):
    actor_id: str
    role: Role
    company_id: str | None = None
    assigned_case_ids: tuple[str, ...] = ()
    demo_impersonation: bool = True
    """Always True in this prototype: local role simulation, not authentication."""


class Enterprise(Contract):
    company_id: str
    synthetic_mf: str
    display_name: str
    sector: str
    created_on: date
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"


# ---------------------------------------------------------------------------
# Documents and extraction
# ---------------------------------------------------------------------------

class Document(Contract):
    document_id: str
    subject_company_id: str
    case_id: str
    original_filename: str
    local_path: str
    sha256: str
    media_type: str
    page_count: int | None = None
    received_at: AwareDatetime
    uploader_actor_id: str
    acquisition_channel: AcquisitionChannel
    asserted_issuer_id: str | None = None
    origin_group_id: str
    source_record_id: str | None = None
    confidentiality_scope: str
    extraction_status: str = "NOT_RUN"
    processing_limitations: tuple[str, ...] = ()
    supersedes_document_id: str | None = None


class EvidenceRef(Contract):
    document_id: str | None = None
    page: int | None = None
    exact_text: str | None = None
    source_record_id: str | None = None
    field_name: str | None = None


class CandidateField(Contract):
    field_name: str
    raw_value: str | None
    normalized_value: str | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()
    ambiguities: tuple[str, ...] = ()


class ExtractionProposal(Contract):
    proposal_id: str
    document_id: str
    candidates: tuple[CandidateField, ...]
    missing_fields: tuple[str, ...] = ()
    mode: Mode
    model_id: str | None = None
    prompt_version: str
    status: Literal["PROPOSED", "CONFIRMED", "REJECTED"] = "PROPOSED"


class PageText(Contract):
    page: int
    text: str


class DocumentText(Contract):
    """Native text extraction result (lane C)."""

    document_id: str
    pages: tuple[PageText, ...]
    status: Literal["OK", "PARTIAL", "UNSUPPORTED", "ERROR"]
    limitations: tuple[str, ...] = ()


class RouterResult(Contract):
    """Jev (or labelled fallback) document/purpose classification (lane C)."""

    document_id: str
    candidate_class: DocumentClass | PurposeCategory
    uncertainty: DecimalStr | None = None
    model_id: str | None = None
    mode: Mode


class IntegrityReport(Contract):
    """Byte integrity and provenance inventory; never an authenticity verdict."""

    document_id: str
    sha256: str
    metadata: dict[str, str] = Field(default_factory=dict)
    signature_status: Literal["UNSIGNED", "NOT_CHECKED", "UNSUPPORTED", "INVALID", "VALID_IN_CONFIGURED_CONTEXT"] = "NOT_CHECKED"
    c2pa_status: Literal["ABSENT", "NOT_CHECKED", "UNSUPPORTED", "PRESENT_UNVERIFIED", "VALID_IN_CONFIGURED_CONTEXT"] = "NOT_CHECKED"
    ai_origin: Literal["UNKNOWN"] = "UNKNOWN"
    limitations: tuple[str, ...] = ()


class RetrievedPassage(Contract):
    """Candidate legal/reference passage; relevance is not applicability."""

    rule_id: str
    source_url: str
    document_title: str
    page: int | None = None
    article: str | None = None
    language: str
    jurisdiction: str
    review_status: str
    text: str
    score: DecimalStr | None = None
    mode: Mode


# ---------------------------------------------------------------------------
# Invoices, transactions, settlements
# ---------------------------------------------------------------------------

class InvoiceLine(Contract):
    line_id: str
    item_description: str
    normalized_item_code: str | None = None
    quantity: DecimalStr
    unit: str
    unit_price_millimes: Millimes
    line_net_millimes: Millimes
    tax_rate: DecimalStr | None = None
    project_id: str | None = None


class InvoiceObservation(Contract):
    observation_id: str
    document_id: str
    transaction_id: str | None = None
    perspective: Perspective
    issuer_company_id: str | None = None
    issuer_mf_raw: str | None = None
    buyer_company_id: str | None = None
    buyer_mf_raw: str | None = None
    invoice_number: str
    invoice_version: str | None = None
    issued_on: date
    available_at: AwareDatetime
    currency: Currency
    net_millimes: Millimes
    tax_millimes: Millimes
    gross_millimes: Millimes
    referenced_invoice_id: str | None = None
    lines: tuple[InvoiceLine, ...] = ()
    transcription_status: str
    origin_group_id: str


class Transaction(Contract):
    transaction_id: str
    buyer_company_id: str
    seller_company_id: str | None = None
    invoice_observation_ids: tuple[str, ...]
    project_id: str | None = None
    economic_period: str
    source_coverage: str
    correlation_status: str
    canonical_revision: int


class Payment(Contract):
    payment_id: str
    source_record_id: str
    payer_company_id: str | None = None
    payee_company_id: str | None = None
    payer_mapping_ref: str | None = None
    payee_mapping_ref: str | None = None
    currency: Currency
    amount_millimes: NonNegMillimes
    status: PaymentStatus
    occurred_at: AwareDatetime
    available_at: AwareDatetime
    origin_group_id: str


class PaymentAllocation(Contract):
    payment_id: str
    transaction_id: str
    allocated_millimes: NonNegMillimes
    accepted_by: str
    accepted_at: AwareDatetime


class SettlementAdjustment(Contract):
    adjustment_id: str
    transaction_id: str
    kind: str
    signed_millimes: Millimes
    supporting_refs: tuple[str, ...] = ()
    accepted_by: str | None = None
    status: AllocationStatus


class IdentityMapping(Contract):
    """Supplied payer/payee mapping provenance; a printed MF is not one."""

    mapping_id: str
    company_id: str
    source_record_id: str
    status: str
    verified_by: str | None = None


class Delivery(Contract):
    delivery_id: str
    transaction_id: str
    item_code: str
    quantity: DecimalStr
    unit: str
    received_at: date
    source_refs: tuple[str, ...] = ()
    status: str


# ---------------------------------------------------------------------------
# Purpose / context
# ---------------------------------------------------------------------------

class ContextClaim(Contract):
    """Company-declared claim. Never proof; always attributed."""

    claim_id: str
    company_id: str
    transaction_id: str | None = None
    project_id: str | None = None
    purpose_category: PurposeCategory
    purpose_text: str
    beneficiary_type: str
    planned_start: date | None = None
    planned_end: date | None = None
    stage: str | None = None
    reported_stock_qty: DecimalStr | None = None
    author_actor_id: str
    submitted_at: AwareDatetime
    supersedes_claim_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    verification_status: Literal["COMPANY_DECLARED"] = "COMPANY_DECLARED"
    declared_horizon: HorizonBucket = HorizonBucket.UNKNOWN
    """Explicit company declaration only. Never derived from dates or model output;
    a change is recorded as a new superseding claim."""


class Project(Contract):
    project_id: str
    company_id: str
    label: str
    project_type: str
    planned_start: date | None = None
    planned_end: date | None = None
    reference_ids: tuple[str, ...] = ()
    status: str


class QuantityReference(Contract):
    reference_id: str
    company_id: str
    project_id: str
    item_code: str
    unit: str
    baseline_kind: BaselineKind
    quantity: DecimalStr
    valid_from: date
    valid_to: date | None = None
    source_refs: tuple[str, ...] = ()
    acceptance_status: str
    accepted_by: str | None = None


class Allocation(Contract):
    allocation_id: str
    transaction_id: str
    line_id: str
    target_project_id: str | None = None
    target_type: AllocationTarget
    quantity: DecimalStr
    unit: str
    effective_on: date
    source_refs: tuple[str, ...] = ()
    status: AllocationStatus
    fact_kind: str | None = None
    independent_verification: bool = False


# ---------------------------------------------------------------------------
# Findings, hypotheses, scenarios, scores
# ---------------------------------------------------------------------------

class Finding(Contract):
    """Supported observation for human review. No fraud probability."""

    finding_id: str
    case_id: str
    company_id: str
    transaction_id: str
    family: FindingFamily
    status: FindingStatus
    severity: DecimalStr | None = None
    financial_basis: str | None = None
    observed_difference_millimes: Millimes | None = None
    quantity_difference: DecimalStr | None = None
    unit: str | None = None
    evidence_refs: tuple[EvidenceRef, ...] = ()
    assumption_ids: tuple[str, ...] = ()
    missing_evidence_types: tuple[str, ...] = ()
    reason_code: str | None = None
    calculation_version: str
    case_version: int


class Hypothesis(Contract):
    hypothesis_id: str
    statement_template_id: str
    supporting_refs: tuple[EvidenceRef, ...] = ()
    contradicting_refs: tuple[EvidenceRef, ...] = ()
    missing_evidence_types: tuple[str, ...] = ()
    test_id: str
    status: HypothesisStatus
    scope: str
    case_version: int


class Scenario(Contract):
    """Sensitivity analysis. Always hypothetical, never mutates canonical state."""

    scenario_id: str
    label: str
    assumption_ids: tuple[str, ...] = ()
    inputs: dict[str, str]
    outputs: dict[str, str]
    hypothetical: Literal[True] = True
    evidence_refs: tuple[EvidenceRef, ...] = ()
    changes_canonical_state: Literal[False] = False


class ScoreResult(Contract):
    """One transaction's review-priority baseline (lane B)."""

    transaction_id: str
    review_index: int | None
    evidence_coverage: DecimalStr | None
    coverage_complete: bool
    evaluable_families: tuple[FindingFamily, ...] = ()
    unknown_families: tuple[FindingFamily, ...] = ()
    contributions: dict[str, DecimalStr] = Field(default_factory=dict)
    method: str
    not_fraud_probability: Literal[True] = True


class CauseProgress(Contract):
    transaction_id: str
    family: FindingFamily
    raw_contribution: DecimalStr
    current_contribution: DecimalStr
    stage: ProgressStage
    provisional: bool
    reason_code: str | None = None
    source_ids: tuple[str, ...] = ()


class ScoreSnapshot(Contract):
    company_id: str
    case_version: int
    cutoff: AwareDatetime
    method_id: str
    rules_version: str
    review_index: int | None
    raw_review_index: int | None = None
    cause_progress: tuple[CauseProgress, ...] = ()
    decisive_transaction_id: str | None = None
    evidence_coverage: DecimalStr | None
    coverage_complete: bool
    contributions: dict[str, DecimalStr] = Field(default_factory=dict)
    tested_families: tuple[FindingFamily, ...] = ()
    unknown_families: tuple[FindingFamily, ...] = ()
    scope_note: str
    unresolved_distinct_transactions: int
    clarification_status: ClarificationStatus
    not_fraud_probability: Literal[True] = True


class TransactionInputs(Contract):
    """Everything lane B's pure checks need for one transaction, scoped by A."""

    case_id: str
    company_id: str
    case_version: int
    as_of: AwareDatetime
    transaction: Transaction
    invoice_observations: tuple[InvoiceObservation, ...]
    payments: tuple[Payment, ...] = ()
    payment_allocations: tuple[PaymentAllocation, ...] = ()
    settlement_adjustments: tuple[SettlementAdjustment, ...] = ()
    identity_mappings: tuple[IdentityMapping, ...] = ()
    allocations: tuple[Allocation, ...] = ()
    quantity_references: tuple[QuantityReference, ...] = ()
    context_claims: tuple[ContextClaim, ...] = ()
    deliveries: tuple[Delivery, ...] = ()
    documents: tuple[Document, ...] = ()


# ---------------------------------------------------------------------------
# Clarification, evidence acceptance, revisions
# ---------------------------------------------------------------------------

class Question(Contract):
    question_id: str
    text_fr: str
    answer_kind: Literal["TEXT", "PROJECT", "DATE_RANGE", "QUANTITY", "DOCUMENT", "CHOICE"] = "TEXT"
    choices: tuple[str, ...] = ()
    related_fact_ids: tuple[str, ...] = ()


class ClarificationRequest(Contract):
    request_id: str
    case_id: str
    company_id: str
    case_version: int
    fact_ids: tuple[str, ...] = ()
    question_ids: tuple[str, ...] = ()
    allowed_document_types: tuple[DocumentClass, ...] = ()
    target_response_at: AwareDatetime | None = None
    target_kind: Literal["DEMO_SERVICE_TARGET"] = "DEMO_SERVICE_TARGET"
    status: RequestStatus
    approved_by: str | None = None
    published_at: AwareDatetime | None = None
    available_in_inbox_at: AwareDatetime | None = None
    origin: Literal["OFFICER", "AUTOMATIC"] = "OFFICER"
    """AUTOMATIC: neutral fixed-catalogue request published by the service after a company
    submission (no human approval, ``approved_by`` stays None). Never a decision."""
    reason_codes: tuple[str, ...] = ()
    """Deterministic codes (context consistency / finding reasons) that led to the questions."""
    reason_text_fr: str | None = None
    overdue_state: Literal["ON_TRACK", "FOLLOW_UP_DUE"] | None = None
    """Read-time only (demo target vs clock) for requests awaiting a response; never stored."""


class ClarificationResponse(Contract):
    response_id: str
    request_id: str
    author_actor_id: str
    claim_ids: tuple[str, ...] = ()
    document_ids: tuple[str, ...] = ()
    answers: dict[str, str] = Field(default_factory=dict)
    submitted_at: AwareDatetime


class AllocationChange(Contract):
    """One scoped change inside an evidence proposal."""

    action: Literal["REPLACE", "CREATE"]
    allocation_id: str
    target_project_id: str | None = None
    target_type: AllocationTarget = AllocationTarget.PROJECT
    old_quantity: DecimalStr | None = None
    new_quantity: DecimalStr


class EvidenceProposal(Contract):
    """Candidate change from a company response; nothing changes until accepted."""

    proposal_id: str
    case_id: str
    expected_version: int
    source_document_id: str | None = None
    source_response_id: str | None = None
    transaction_id: str
    line_id: str
    unit: str
    budget_quantity: DecimalStr
    changes: tuple[AllocationChange, ...]
    status: ProposalStatus


class EvidenceAcceptance(Contract):
    proposal_id: str
    case_id: str
    expected_version: int
    scoped_changes: tuple[AllocationChange, ...]
    actor_id: str
    idempotency_key: str
    reason: str | None = None


class CaseRevision(Contract):
    case_id: str
    version: int
    parent_version: int | None = None
    accepted_evidence_ids: tuple[str, ...] = ()
    fact_hash: str
    score_snapshot: ScoreSnapshot | None = None
    created_at: AwareDatetime
    reason: str


class ActionReceipt(Contract):
    idempotency_key: str
    action: str
    case_id: str
    actor_id: str
    input_hash: str
    resulting_version: int
    result_hash: str


class CaseEvent(Contract):
    """Local traceability record (not tamper-proof legal evidence)."""

    event_id: str
    case_id: str
    kind: str
    actor_id: str
    at: AwareDatetime
    case_version: int
    summary: str
    fact_ids: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Service views (what the UI receives)
# ---------------------------------------------------------------------------

class DocumentView(Contract):
    document: Document
    extraction: ExtractionProposal | None = None
    integrity: IntegrityReport | None = None
    routing: RouterResult | None = None
    """Candidate document class (Jev or MANUAL fallback). Never an input to checks or scores."""
    case_version: int
    mode: Mode


class TransactionSummary(Contract):
    """Invoiced, settled and declared flows kept separate — never summed."""

    transaction_id: str
    counterparty_company_id: str | None
    counterparty_display_name: str | None
    invoice_number: str | None
    issued_on: date | None
    invoiced_gross_millimes: Millimes | None
    settled_millimes: Millimes | None
    declared_millimes: Millimes | None = None
    observation_perspectives: tuple[Perspective, ...] = ()
    corroboration_status: str
    project_id: str | None = None


class ContextAssessmentView(Contract):
    """Declared / interpreted / calculated project context, side by side.

    Clarification aid only: never a finding, score contribution, risk or fraud label.
    Interpreted values are model suggestions; supporting spans are exact substrings of
    the company's own purpose text. Corroboration is not assessed by this layer.
    """

    claim_id: str
    declared_horizon: HorizonBucket
    interpreted_horizon: HorizonBucket
    calculated_horizon: HorizonBucket
    declared_purpose_category: PurposeCategory
    interpreted_purpose_category: PurposeCategory
    duration_days: int | None
    consistency_status: Literal["CONSISTENT", "NEEDS_CLARIFICATION", "INSUFFICIENT"]
    reason_codes: tuple[str, ...] = ()
    recommended_question_ids: tuple[str, ...] = ()
    supporting_spans: tuple[str, ...] = ()
    corroboration_status: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    interpretation_mode: Mode
    horizon_convention_fr: str = ("Convention de démonstration BOUSSLA : 0 à 90 jours = court ; 91 jours ou plus = "
                                  "plus long. Ce n'est pas une classification juridique, fiscale ou comptable.")


class CompanyCaseView(Contract):
    """Company audience: own records, own claims, published questions only.

    Deliberately has no review index, findings, internal ranking or
    counterparty tax status.
    """

    audience: Literal[Audience.COMPANY] = Audience.COMPANY
    case_id: str
    company_id: str
    company_display_name: str
    case_version: int
    documents: tuple[DocumentView, ...] = ()
    transactions: tuple[TransactionSummary, ...] = ()
    projects: tuple[Project, ...] = ()
    context_claims: tuple[ContextClaim, ...] = ()
    allocations: tuple[Allocation, ...] = ()
    pending_transcriptions: tuple[ExtractionProposal, ...] = ()
    open_questions: tuple[Question, ...] = ()
    inbox: tuple["RequestView", ...] = ()
    responses: tuple[ClarificationResponse, ...] = ()
    context_assessment: ContextAssessmentView | None = None
    capabilities: "CaseCapabilities" = Field(default_factory=lambda: CaseCapabilities())
    mode: Mode
    banner_fr: str


class GroundedNoteView(Contract):
    """Officer-only, citation-checked synthesis over retrieved public passages.

    Display data only: never a canonical fact, accepted evidence or score input,
    and never an applicability decision. No prompt, response body or case data.
    """

    summary_fr: str
    candidate_rule_ids: tuple[str, ...]
    applicability_questions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    provider_model: str | None = None
    generation_mode: Mode
    disclaimer_fr: str = "Synthèse indicative — l'applicabilité doit être vérifiée par l'agent."


class OperationalConfidenceFactor(Contract):
    code: Literal["TIMELINESS", "ANSWER_COHERENCE", "EVIDENCE_CORROBORATION", "HISTORICAL_STABILITY"]
    numerator: int = Field(ge=0)
    denominator: int = Field(gt=0)
    nominal_weight: int = Field(ge=0, le=100)
    effective_weight: DecimalStr
    weighted_contribution: DecimalStr
    reason_codes: tuple[str, ...]
    source_ids: tuple[str, ...]
    explanation_fr: str


class OperationalConfidence(Contract):
    index: int | None = Field(default=None, ge=0, le=100)
    status: Literal["INSUFFICIENT_DATA", "AVAILABLE"]
    as_of: AwareDatetime
    factors: tuple[OperationalConfidenceFactor, ...] = ()
    eligible_observations: int = 0
    method: str = "OPERATIONAL_CONFIDENCE_V2"


class ConfidenceFactorDelta(Contract):
    code: str
    before_contribution: DecimalStr | None = None
    after_contribution: DecimalStr | None = None
    before_numerator: int | None = None
    before_denominator: int | None = None
    after_numerator: int | None = None
    after_denominator: int | None = None
    source_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


class ConfidenceHistoryEntry(Contract):
    from_version: int
    to_version: int
    as_of: AwareDatetime
    before_index: int | None = None
    after_index: int | None = None
    before_status: Literal["INSUFFICIENT_DATA", "AVAILABLE"]
    after_status: Literal["INSUFFICIENT_DATA", "AVAILABLE"]
    factor_deltas: tuple[ConfidenceFactorDelta, ...] = ()


class OfficerCaseView(Contract):
    audience: Literal[Audience.OFFICER] = Audience.OFFICER
    case_id: str
    company_id: str
    company_display_name: str
    case_version: int
    documents: tuple[DocumentView, ...] = ()
    transactions: tuple[TransactionSummary, ...] = ()
    invoice_observations: tuple[InvoiceObservation, ...] = ()
    payments: tuple[Payment, ...] = ()
    projects: tuple[Project, ...] = ()
    context_claims: tuple[ContextClaim, ...] = ()
    quantity_references: tuple[QuantityReference, ...] = ()
    allocations: tuple[Allocation, ...] = ()
    findings: tuple[Finding, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    scenarios: tuple[Scenario, ...] = ()
    score: ScoreSnapshot | None = None
    requests: tuple["RequestView", ...] = ()
    responses: tuple[ClarificationResponse, ...] = ()
    proposals: tuple[EvidenceProposal, ...] = ()
    candidate_passages: tuple[RetrievedPassage, ...] = ()
    reference_note: GroundedNoteView | None = None
    context_assessment: ContextAssessmentView | None = None
    """Officer-only; CompanyCaseView deliberately has no equivalent."""
    triage: "TriageAssessment | None" = None
    """Officer-only queue urgency, separate from ``score.review_index``."""
    clarification_deadlines: tuple["ClarificationDeadlineView", ...] = ()
    history_signals: tuple["CompanyHistorySignal", ...] = ()
    history_signal_index: int | None = None
    history_signal_status: Literal["INSUFFICIENT_DATA", "AVAILABLE"] = "INSUFFICIENT_DATA"
    history_signal_factors: tuple["HistoricalFactor", ...] = ()
    history_signal_method: str | None = None
    operational_confidence_index: int | None = None
    operational_confidence_status: Literal["INSUFFICIENT_DATA", "AVAILABLE"] = "INSUFFICIENT_DATA"
    operational_confidence_as_of: AwareDatetime | None = None
    operational_confidence_factors: tuple[OperationalConfidenceFactor, ...] = ()
    operational_confidence_eligible_observations: int = 0
    operational_confidence_method: str = "OPERATIONAL_CONFIDENCE_V2"
    investigator_brief: "InvestigatorBriefView | None" = None
    enterprise_profile: "EnterpriseProfileView | None" = None
    monthly_activity: tuple["MonthlyActivityView", ...] = ()
    payment_timeline: tuple["PaymentTimelineEntry", ...] = ()
    financial_snapshot: "FinancialSnapshotView | None" = None
    invoice_comparisons: tuple["InvoiceComparisonView", ...] = ()
    deliveries: tuple[Delivery, ...] = ()
    mode: Mode
    mode_by_node: dict[str, Mode] = Field(default_factory=dict)
    banner_fr: str


class AnalysisView(Contract):
    analysis_id: str
    case_id: str
    case_version: int
    audience: Audience
    status: AnalysisStatus
    questions: tuple[Question, ...] = ()
    question_round: int = 0
    findings: tuple[Finding, ...] = ()
    """Populated for OFFICER audience only."""
    hypotheses: tuple[Hypothesis, ...] = ()
    scenarios: tuple[Scenario, ...] = ()
    score: ScoreSnapshot | None = None
    mode_by_node: dict[str, Mode] = Field(default_factory=dict)
    error_codes: tuple[ErrorCode, ...] = ()
    mode: Mode


class QueueItem(Contract):
    case_id: str
    company_id: str
    company_display_name: str
    case_version: int
    review_index: int | None
    evidence_coverage: DecimalStr | None
    coverage_complete: bool
    active_finding_count: int
    clarification_status: ClarificationStatus
    scope_note: str
    triage_priority: int | None = None
    """Queue urgency (0..100), NOT the review index and NOT a fraud probability."""
    triage_reason_codes: tuple[str, ...] = ()
    sector: str | None = None
    synthetic_identifier: str | None = None
    last_activity_at: date | None = None
    history_signal_codes: tuple[str, ...] = ()
    history_signal_index: int | None = None
    history_anomaly: bool | None = None
    """True when a lane B signal other than NO_SIGNIFICANT_CHANGE/INSUFFICIENT_HISTORY exists."""


class QueuePage(Contract):
    items: tuple[QueueItem, ...]
    next_cursor: str | None = None
    cutoff: AwareDatetime
    mode: Mode


class ClarificationDraft(Contract):
    draft_id: str
    case_id: str
    company_id: str
    case_version: int
    questions: tuple[Question, ...]
    fact_ids: tuple[str, ...] = ()
    allowed_document_types: tuple[DocumentClass, ...] = ()
    target_response_at: AwareDatetime | None = None
    text_fr: str
    status: Literal[RequestStatus.DRAFT] = RequestStatus.DRAFT
    mode: Mode


class RequestView(Contract):
    request: ClarificationRequest
    questions: tuple[Question, ...]
    text_fr: str
    mode: Mode


class ResponseView(Contract):
    response: ClarificationResponse
    proposal_ids: tuple[str, ...] = ()
    case_version: int
    mode: Mode


class RevisionResult(Contract):
    case_id: str
    outcome: Literal["ACCEPTED", "REJECTED"]
    previous_version: int
    new_version: int
    replayed: bool = False
    """True when an identical authorized retry returned the stored outcome."""
    receipt: ActionReceipt
    allocations_before: tuple[Allocation, ...] = ()
    allocations_after: tuple[Allocation, ...] = ()
    findings_before: tuple[Finding, ...] = ()
    findings_after: tuple[Finding, ...] = ()
    score_before: ScoreSnapshot | None = None
    score_after: ScoreSnapshot | None = None
    mode: Mode


class HistoryView(Contract):
    case_id: str
    audience: Audience
    revisions: tuple[CaseRevision, ...]
    events: tuple[CaseEvent, ...]
    mode: Mode


class OfficerHistoryView(HistoryView):
    audience: Literal[Audience.OFFICER] = Audience.OFFICER
    operational_confidence_changes: tuple[ConfidenceHistoryEntry, ...] = ()


class LocalDraftArtifact(Contract):
    artifact_id: str
    case_id: str
    audience: Audience
    case_version: int
    filename: str
    content_markdown: str
    generated_at: AwareDatetime
    mode: Mode
    disclaimer_fr: str


# ---------------------------------------------------------------------------
# Triage, clarification deadlines and cross-lane integration contracts
# (boussla-automation-1, additive)
# ---------------------------------------------------------------------------

class ClarificationDeadlineView(Contract):
    """Demo service target for one clarification request, evaluated at read time.

    Not a legal deadline. Being overdue only raises queue urgency (triage); it never
    creates a finding and never changes the review index.
    """

    request_id: str
    origin: Literal["OFFICER", "AUTOMATIC"]
    status: RequestStatus
    target_response_at: AwareDatetime | None
    target_kind: Literal["DEMO_SERVICE_TARGET"] = "DEMO_SERVICE_TARGET"
    overdue: bool
    overdue_days: int = Field(ge=0)
    note_fr: str = "Date cible de démonstration BOUSSLA ; ce n'est pas un délai légal."


class TriageAssessment(Contract):
    """Operational queue urgency for the officer (0..100), with explicit reason codes.

    Separate from ``ScoreSnapshot.review_index`` (documentary review priority): triage
    may rise because a clarification is pending/overdue or a human decision is waiting,
    none of which is evidence. Never a fraud probability, never a finding.
    """

    case_id: str
    case_version: int
    triage_priority: int = Field(ge=0, le=100)
    review_index: int | None
    """Echo of the deterministic review index used as the base; never modified here."""
    reason_codes: tuple[str, ...] = ()
    components: dict[str, int] = Field(default_factory=dict)
    formula_version: str
    as_of: AwareDatetime
    not_fraud_probability: Literal[True] = True
    note_fr: str = ("Urgence de traitement (démonstration) : n'est ni l'indice de revue ni une probabilité "
                    "de fraude ; une absence de réponse ne crée aucun constat.")


class HistorySignalCode(str, Enum):
    """Lane B neutral history observations (``boussla.history_signals``). Review context only."""

    ACTIVITY_GAP = "ACTIVITY_GAP"
    LATE_DOCUMENT_ACTIVITY = "LATE_DOCUMENT_ACTIVITY"
    VOLUME_SPIKE = "VOLUME_SPIKE"
    VOLUME_DROP = "VOLUME_DROP"
    PAYMENT_PATTERN_CHANGE = "PAYMENT_PATTERN_CHANGE"
    COUNTERPARTY_CONCENTRATION_CHANGE = "COUNTERPARTY_CONCENTRATION_CHANGE"
    REPEATED_INVOICE_CONFLICT = "REPEATED_INVOICE_CONFLICT"
    NO_SIGNIFICANT_CHANGE = "NO_SIGNIFICANT_CHANGE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNUSUAL_DEPOSIT_DELAY = "UNUSUAL_DEPOSIT_DELAY"
    UNUSUAL_AMOUNT_INCREASE = "UNUSUAL_AMOUNT_INCREASE"
    UNUSUAL_AMOUNT_DECREASE = "UNUSUAL_AMOUNT_DECREASE"
    NEW_SUPPLIER = "NEW_SUPPLIER"
    UNUSUAL_SPLIT_PAYMENT = "UNUSUAL_SPLIT_PAYMENT"


class CompanyHistorySignal(Contract):
    """Lane B deterministic history observation, typed for officer views (officer-only).

    Operational review context for queue urgency; not a finding, not evidence, never a
    fraud label and never an input to checks, scores, acceptance or revisions.
    """

    signal_id: str
    company_id: str
    reason_code: HistorySignalCode
    period: str
    metric: str
    observed_value: str
    baseline_value: str | None = None
    baseline_periods: tuple[str, ...] = ()
    evidence_source_ids: tuple[str, ...] = ()
    explanation_fr: str
    method: str
    mode: Mode
    affects_review_index: Literal[False] = False
    affected_transaction_ids: tuple[str, ...] = ()


class HistoricalFactor(Contract):
    reason_code: HistorySignalCode
    contribution: int = Field(ge=0, le=100)
    source_signal_ids: tuple[str, ...]
    explanation_fr: str


class HistoricalIndicator(Contract):
    index: int | None = Field(default=None, ge=0, le=100)
    status: Literal["INSUFFICIENT_DATA", "AVAILABLE"]
    factors: tuple[HistoricalFactor, ...] = ()
    method: str = "HISTORY_CONTEXT_V1"


class BriefObservationView(Contract):
    kind: Literal["FACT", "DECLARATION", "MODEL_INTERPRETATION", "HYPOTHESIS", "HYPOTHETICAL_SCENARIO"]
    text_fr: str
    source_codes: tuple[str, ...] = ()


class BriefHypothesisView(Contract):
    """One fixed-catalogue candidate explanation (lane C). Support is a deterministic label,
    never a probability and never a score contribution."""

    hypothesis_id: str
    name_fr: str
    status: Literal["SUPPORTED", "PLAUSIBLE", "WEAK", "CONTRADICTED", "INSUFFICIENT"]
    supporting_refs: tuple[str, ...] = ()
    contradicting_refs: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    why_it_matters_fr: str


class InvestigatorBriefView(Contract):
    """Officer-only assisted analysis built from lane C's ``InvestigatorBrief`` after the
    deterministic evaluation, history signals, context consistency and public retrieval.

    Cites only known finding evidence, retrieved rule IDs, history codes and catalogue
    hypothesis IDs; suggests allowlisted question IDs only. Never changes the review
    index, facts, evidence acceptance or legal applicability.
    """

    case_id: str
    case_version: int
    summary_fr: str
    key_observations: tuple[BriefObservationView, ...] = ()
    top_hypotheses: tuple[BriefHypothesisView, ...] = Field(default=(), max_length=5)
    missing_information: tuple[str, ...] = ()
    changes_since_previous_version: tuple[str, ...] = ()
    questions_proposed: tuple[str, ...] = Field(default=(), max_length=3)
    questions_already_asked: tuple[str, ...] = ()
    reference_rule_ids: tuple[str, ...] = ()
    history_signal_codes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    mode: Mode
    authoritative: Literal[False] = False
    label_fr: str = "Analyse assistée BOUSSLA"
    disclaimer_fr: str = "L'analyse assistée ne modifie pas l'indice de revue ni les faits du dossier."


class EnterpriseProfileView(Contract):
    company_id: str
    display_name: str
    synthetic_identifier: str
    sector: str
    created_on: date
    activity_start: str | None = None
    activity_end: str | None = None
    portfolio_member: bool = False
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"




class MonthlyActivityView(Contract):
    """Calendar window with explicit covered zero versus unknown ledger coverage."""

    month: str
    transaction_count: int
    invoice_observation_count: int
    settled_outflow_millimes: int
    source_label: str = "Faits synthétiques du dossier"
    coverage_status: Literal["COVERED", "UNKNOWN"] = "UNKNOWN"
    coverage_source_id: str | None = None


class PaymentTimelineEntry(Contract):
    payment_id: str
    transaction_id: str | None = None
    occurred_at: AwareDatetime
    amount_millimes: int
    currency: Currency
    status: PaymentStatus
    origin_group_id: str


class FinancialSnapshotView(Contract):
    """Lane B synthetic authorized snapshot. Context only: no bank access, no proof."""

    label_fr: Literal["Instantané financier synthétique — source autorisée simulée"] = (
        "Instantané financier synthétique — source autorisée simulée")
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    as_of: AwareDatetime
    currency: Currency
    observed_outflows_millimes: int
    observed_settlements_millimes: int
    documented_payable_millimes: int
    outstanding_documented_payable_millimes: int
    inflows_millimes: None = None
    """Not supplied: the synthetic ledger covers purchases only (zero is not a revenue claim)."""
    scope: str
    statement_fr: str
    source_count: int


class InvoiceComparisonView(Contract):
    """Buyer vs seller observation of one transaction, paired by authoritative IDs.
    Differences are computed field by field on the server; agreement is corroboration
    between independent observations, never proof of validity."""

    transaction_id: str
    buyer_observation_id: str | None = None
    seller_observation_id: str | None = None
    status: Literal["CONCORDANT", "DIFFERENCES", "SINGLE_OBSERVATION"]
    label_fr: str
    difference_fields: tuple[str, ...] = ()
    counterparty_reason_code: str | None = None


class CaseCapabilities(Contract):
    supports_null_project_id: bool = True


class AdminEnterpriseView(Contract):
    """Synthetic portfolio enterprise as seen by the local DEMO_OPERATOR only."""

    company_id: str
    display_name: str
    sector: str
    synthetic_identifier: str
    case_id: str
    case_version: int | None = None
    transaction_count: int
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"


class AdminPortfolioResult(Contract):
    action: Literal["SEED", "RESET", "ADD", "DELETE"]
    enterprise_count: int
    case_ids: tuple[str, ...] = ()
    notice_fr: str = "Administration de données synthétiques — démonstration locale."


CompanyCaseView.model_rebuild()
OfficerCaseView.model_rebuild()


# ---------------------------------------------------------------------------
# Interfaces other lanes implement / consume
# ---------------------------------------------------------------------------

@runtime_checkable
class ChecksEngine(Protocol):
    """Lane B: deterministic, pure; no clock, network, model or randomness."""

    def evaluate_transaction(self, inputs: TransactionInputs) -> list[Finding]: ...

    def run_scenarios(self, inputs: TransactionInputs, config: dict) -> list[Scenario]: ...

    def score_transaction(self, findings: list[Finding], applicability: set[FindingFamily]) -> ScoreResult: ...

    def aggregate_company(self, transaction_scores: list[ScoreResult]) -> int | None: ...


@runtime_checkable
class TextExtractor(Protocol):
    """Lane C: native PDF text with page/size limits."""

    def extract_text(self, document: Document, content: bytes) -> DocumentText: ...


@runtime_checkable
class DocumentRouter(Protocol):
    """Lane C: Jev classification or a labelled fallback."""

    def classify(self, document_id: str, text: str, allowed: tuple[str, ...]) -> RouterResult: ...


@runtime_checkable
class FieldExtractor(Protocol):
    """Lane C: candidate invoice fields with exact spans; nulls for missing."""

    def extract_fields(self, text: DocumentText) -> ExtractionProposal: ...


@runtime_checkable
class ReferenceRetriever(Protocol):
    """Lane C: Qdrant local (or labelled lexical) legal/reference retrieval."""

    def search(self, query: str, *, as_of: date, jurisdiction: str, audience: Audience, limit: int = 5) -> list[RetrievedPassage]: ...


@runtime_checkable
class CompanyHistorySignalProvider(Protocol):
    """Lane B: history/portfolio signals for one company as of a date (pure, local)."""

    def signals(self, company_id: str, as_of: date) -> list[CompanyHistorySignal]: ...


@runtime_checkable
class IntegrityInspector(Protocol):
    def inspect(self, document: Document, content: bytes) -> IntegrityReport: ...


@runtime_checkable
class BousslaService(Protocol):
    """The only public entry point for UI reads/writes (CONTRACTS.md §3)."""

    def create_case(self, actor: Actor, company_id: str, project_payload: dict, request_id: str) -> CompanyCaseView | OfficerCaseView: ...

    def upload_document(self, actor: Actor, case_id: str, upload_bytes: bytes, filename: str, media_type: str, expected_version: int, request_id: str, response_id: str | None = None) -> DocumentView: ...

    def confirm_transcription(self, actor: Actor, case_id: str, proposal_id: str, field_confirmations: dict[str, str], expected_version: int, request_id: str) -> CompanyCaseView: ...

    def submit_context(self, actor: Actor, case_id: str, context_payload: dict, expected_version: int, request_id: str) -> CompanyCaseView: ...

    def start_analysis(self, actor: Actor, case_id: str, expected_version: int) -> AnalysisView: ...

    def answer_questions(self, actor: Actor, case_id: str, analysis_id: str, answers: dict[str, str], expected_version: int, request_id: str) -> AnalysisView: ...

    def get_case(self, actor: Actor, case_id: str) -> CompanyCaseView | OfficerCaseView: ...

    def list_queue(self, actor: Actor, cutoff: object, limit: int, cursor: str | None = None) -> QueuePage: ...

    def prepare_clarification(self, actor: Actor, case_id: str, expected_version: int) -> ClarificationDraft: ...

    def publish_clarification(self, actor: Actor, case_id: str, draft_id: str, expected_version: int, request_id: str) -> RequestView: ...

    def submit_response(self, actor: Actor, case_id: str, request_id: str, payload: dict, expected_version: int, idempotency_key: str) -> ResponseView: ...

    def accept_evidence(self, actor: Actor, case_id: str, proposal_id: str, expected_version: int, idempotency_key: str) -> RevisionResult: ...

    def reject_evidence(self, actor: Actor, case_id: str, proposal_id: str, expected_version: int, reason: str, idempotency_key: str) -> RevisionResult: ...

    def get_history(self, actor: Actor, case_id: str) -> HistoryView: ...

    def export_dossier(self, actor: Actor, case_id: str, audience: Audience, expected_version: int) -> LocalDraftArtifact: ...
