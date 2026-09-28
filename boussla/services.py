"""Real application service — lane A. The only public entry point for UI writes.

Every method: (1) resolves the actor server-side and checks role + enterprise
scope, (2) for writes, opens ONE SQLite write transaction that checks the
action receipt first (identical retry -> stored outcome, reused key with other
input -> IDEMPOTENCY_CONFLICT), then the expected version, then scope, then
writes facts + revision + events + receipt atomically. Model/extraction calls
run BEFORE the transaction; none run inside it. Calculations come from the
ChecksEngine (lane B, or the labelled interim adapter), never from here or the UI.

Factory: ``build_service()``. Tests may inject any store/registry/engine.
"""
from __future__ import annotations

import hashlib
import io
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import ValidationError

from boussla.config import Settings, get_settings, use_os_trust_store
from boussla.contracts import (
    Actor, Allocation, AllocationChange, AllocationStatus, AllocationTarget, AnalysisStatus, AnalysisView,
    Audience, BousslaError, ClarificationDraft, ClarificationRequest, ClarificationResponse, ClarificationStatus,
    CompanyCaseView, ContextClaim, Delivery, Document, DocumentAnalysisReport, DocumentView, ErrorCode, EvidenceProposal, Finding,
    FindingFamily, FindingStatus, HistoryView, Hypothesis, IdentityMapping, IntegrityReport, InvoiceObservation,
    LocalDraftArtifact, Mode, OfficerCaseView, OfficerHistoryView, Payment, PaymentAllocation, PaymentStatus, Perspective, Project,
    ProposalStatus, PurposeCategory, QuantityReference, QueueItem, QueuePage, RequestStatus, RequestView,
    ResponseView, RevisionResult, Role, Scenario, ScoreSnapshot, Transaction, TransactionInputs,
    TransactionSummary, ActionReceipt, ExtractionProposal, DocumentClass, DocumentText, RouterResult,
    CompanyHistorySignal, SettlementAdjustment, InvestigatorBriefView, BriefObservationView, BriefHypothesisView,
    EnterpriseProfileView, MonthlyActivityView, PaymentTimelineEntry, InvoiceComparisonView, HorizonBucket,
    AdminEnterpriseView, AdminPortfolioResult, Enterprise, ResolutionImpact,
)
from boussla.interim_checks import InterimChecks, get_checks_engine
from boussla.playbook import (
    merge_question_plan,
    ALLOWED_RESPONSE_DOCUMENTS, AUTO_REQUEST_TEXT_FR, MAX_QUESTIONS_PER_ROUND, QUESTIONS, REQUEST_TEXT_FR,
    deterministic_plan, scoped_questions, fully_asked_questions,
)
from boussla.security import DEMO_BANNER_FR, ActorRegistry, authorize
from boussla.seed import load_enterprises, seed_demo_case
from boussla.store import CaseStore, ReceiptNote, stable_hash, utcnow
from boussla.observability import traced
from boussla.triage import ANOMALY_CODES, PENDING_STATUSES, assess_triage, clarification_deadlines
from boussla.review_evidence import derive_progress_evidence
from boussla.review_progress import RULE_VERSION, calculate_progress, transaction_progress_index
from boussla.historical_indicator import calculate_historical_indicator
from boussla.operational_confidence import calculate_operational_confidence, confidence_window_start
from boussla.monthly_context import build_monthly_context
from boussla.confidence_history import confidence_delta
from boussla.impact import simulate_resolution
from boussla.network import NetworkView, build_network
from boussla.investigation import InvestigationAnswer, answer_investigation

ALL_FAMILIES = frozenset(FindingFamily)
AUTO_ACTOR_ID = "SYSTEM-AUTO-CLARIFICATION"
AUTO_REASON_TEXT_FR = "Précisions demandées automatiquement à partir des informations disponibles."
# Human-readable names for lane C's fixed hypothesis catalogue (presentation only).
HYPOTHESIS_NAMES_FR = {
    "SECOND_PROJECT_ALLOCATION": "Affectation à un second projet",
    "STOCK_REMAINING": "Stock restant",
    "PARTIAL_DELIVERY": "Livraison partielle",
    "CREDIT_NOTE_OR_REVERSAL": "Avoir ou annulation",
    "PAYMENT_SCHEDULE": "Échéancier de paiement",
    "SELLER_TRANSCRIPTION_ERROR": "Transcription côté vendeur à vérifier",
    "BUYER_TRANSCRIPTION_ERROR": "Transcription côté acheteur à vérifier",
    "LATER_INVOICE_CORRECTION": "Correction ultérieure de facture",
    "UNIT_OR_ITEM_MAPPING_ISSUE": "Unité ou article à rapprocher",
    "MISSING_SUPPORTING_DOCUMENT": "Pièce justificative manquante",
}
# Deterministic playbook hypotheses (checks engine) -> lane C catalogue evidence features.
PLAYBOOK_TO_CATALOGUE = {"SECOND_AUTHORIZED_PACKAGE": "SECOND_PROJECT_ALLOCATION",
                         "AUTHORIZED_STOCK": "STOCK_REMAINING"}
"""Author of automatic clarification events. Not an Actor: it cannot call the service."""

# Input contracts for dictionary payloads: any other property is a typed INVALID_INPUT
# (never silently dropped). Identity/scope fields are also rejected by the web adapter.
CONTEXT_FIELDS = frozenset({"project_id", "transaction_id", "purpose_category", "purpose_text", "beneficiary_type",
                            "planned_start", "planned_end", "stage", "reported_stock_qty", "supersedes_claim_id",
                            "declared_horizon"})
RESPONSE_FIELDS = frozenset({"answers", "document_ids", "allocation"})
ALLOCATION_FIELDS = frozenset({"transaction_id", "line_id", "splits", "unit"})
# Plain non-negative decimal quantity: no sign, exponent, NaN/Infinity; bounded size.
_QUANTITY = re.compile(r"\d{1,12}(\.\d{1,6})?")


def _reject_unexpected(payload: object, allowed: frozenset[str], what: str) -> dict:
    if not isinstance(payload, dict):
        raise BousslaError(ErrorCode.INVALID_INPUT, f"{what} : objet attendu")
    unexpected = sorted(str(k) for k in payload if k not in allowed)
    if unexpected:
        raise BousslaError(ErrorCode.INVALID_INPUT, f"{what} : propriété(s) non prévue(s) : " + ", ".join(unexpected),
                           fields=unexpected)
    return payload


def _quantity(raw: object) -> str:
    """User-supplied quantity -> canonical decimal string, or a typed error. Rejects
    booleans/floats, signs, exponents, NaN/Infinity and absurd magnitudes before any
    Decimal arithmetic can overflow."""
    text = raw.strip() if isinstance(raw, str) else str(raw) if type(raw) is int else None
    if text is None or not _QUANTITY.fullmatch(text):
        raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Quantité invalide (nombre décimal positif attendu)")
    whole, _, frac = text.partition(".")
    frac = frac.rstrip("0")
    return f"{int(whole)}.{frac}" if frac else str(int(whole))


def _validated(model, **fields):
    """Build a contract object from user input; invalid values become a typed
    INSUFFICIENT_INFORMATION error (never an unhandled ValidationError)."""
    try:
        obj = model(**fields)
    except ValidationError as exc:
        bad = sorted({str(e["loc"][0]) for e in exc.errors() if e.get("loc")})
        raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Valeur invalide : " + ", ".join(bad), fields=bad) from None
    start, end = getattr(obj, "planned_start", None), getattr(obj, "planned_end", None)
    if start and end and end < start:
        raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "La fin prévue précède le début prévu",
                           fields=["planned_start", "planned_end"])
    return obj
FOLLOW_UP_DAYS = 7


class _GuardedNoteGenerator:
    """Any note-generation error only drops the note; retrieved passages always survive."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def generate(self, reasons, passages):
        try:
            return self._inner.generate(reasons, passages)
        except Exception:  # noqa: BLE001 - provider/client failure is never fatal or a finding
            return None


class _GuardedInterpreter:
    """Any interpreter error becomes an UNKNOWN/TEMPLATE interpretation, so the
    deterministic date comparison still runs when the provider fails."""

    def __init__(self, inner) -> None:
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def interpret(self, context):
        try:
            return self._inner.interpret(context)
        except Exception:  # noqa: BLE001 - provider/client failure is never fatal or a finding
            from boussla.context.models import unknown_interpretation
            return unknown_interpretation(Mode.TEMPLATE, "MODEL_RESPONSE_UNUSABLE")


# =============================================================== demo administration
# Synthetic data only, DEMO_OPERATOR only. Lane B's pure functions produce the new portfolio
# state; this layer authorizes, persists and (re)materializes the enterprise cases.
def _require_portfolio(svc: "BousslaAppService"):
    if svc.portfolio is None:
        raise BousslaError(ErrorCode.INVALID_STATE, "Portefeuille synthétique désactivé")
    return svc.portfolio


def _admin_view(svc: "BousslaAppService", e: Enterprise) -> AdminEnterpriseView:
    case_id = svc.portfolio.case_id(e.company_id)
    exists = svc.store.case_exists(case_id)
    return AdminEnterpriseView(
        company_id=e.company_id, display_name=e.display_name, sector=e.sector, synthetic_identifier=e.synthetic_mf,
        case_id=case_id, case_version=svc.store.case_meta(case_id)["version"] if exists else None,
        transaction_count=len(svc.portfolio.bundle(e.company_id)["events"]))


def _officers(svc: "BousslaAppService"):
    return [a.actor_id for a in svc.registry.actors.values() if a.role is Role.OFFICER]


def _materialize(svc: "BousslaAppService") -> list[str]:
    portfolio = _require_portfolio(svc)
    case_ids = portfolio.materialize_all(svc.store)
    svc.enterprises.update({e.company_id: e for e in portfolio.enterprises()})
    for officer in _officers(svc):
        for case_id in case_ids:
            svc.registry.assign(officer, case_id)
    return case_ids


def _drop_enterprise_case(svc: "BousslaAppService", company_id: str) -> None:
    case_id = svc.portfolio.case_id(company_id)
    svc.store.delete_case(case_id)
    svc.registry.unassign(case_id)
    svc.enterprises.pop(company_id, None)
    svc._brief_questions.pop(case_id, None)
    svc._brief_cache.clear()
    svc._reference_cache.clear()
    svc._context_cache.clear()


class _DemoAdministration:
    """Base of BousslaAppService: synthetic demo administration, apart from the case workflow."""

    def admin_list_enterprises(self, actor: Actor) -> tuple[AdminEnterpriseView, ...]:
        authorize(self.registry, actor, "admin_list_enterprises")
        portfolio = _require_portfolio(self)
        return tuple(_admin_view(self, e) for e in portfolio.enterprises())

    def admin_seed_portfolio(self, actor: Actor) -> AdminPortfolioResult:
        """Materialize any missing portfolio case (idempotent; never overwrites a case)."""
        authorize(self.registry, actor, "admin_seed_portfolio")
        case_ids = _materialize(self)
        return AdminPortfolioResult(action="SEED", enterprise_count=len(case_ids), case_ids=tuple(case_ids))

    def admin_reset_portfolio(self, actor: Actor, confirm: str) -> AdminPortfolioResult:
        """Explicit destructive reset of synthetic portfolio cases to lane B's defaults."""
        authorize(self.registry, actor, "admin_reset_portfolio")
        portfolio = _require_portfolio(self)
        if confirm != "RESET":
            raise BousslaError(ErrorCode.INVALID_INPUT, "Confirmation « RESET » requise", fields=["confirm"])
        for e in portfolio.enterprises():
            _drop_enterprise_case(self, e.company_id)
        portfolio.reset()
        case_ids = _materialize(self)
        return AdminPortfolioResult(action="RESET", enterprise_count=len(case_ids), case_ids=tuple(case_ids))

    def admin_add_enterprise(self, actor: Actor, payload: dict, request_id: str) -> AdminEnterpriseView:
        """Add an empty synthetic enterprise (identity only, no claimed coverage). The ID is
        derived from the idempotency key, so a retried request returns the same enterprise."""
        authorize(self.registry, actor, "admin_add_enterprise")
        portfolio = _require_portfolio(self)
        _reject_unexpected(payload, frozenset({"display_name", "sector"}), "Entreprise")
        name, sector = payload.get("display_name"), payload.get("sector")
        if not isinstance(name, str) or not isinstance(sector, str) or not name.strip() or not sector.strip():
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Nom et secteur requis", fields=["display_name", "sector"])
        suffix = stable_hash(["admin_add_enterprise", request_id])[:6].upper()
        company_id = f"SYN-USR-{suffix}"
        if not portfolio.is_member(company_id):
            clean_name = name.strip()[:80]
            portfolio.add(Enterprise(
                company_id=company_id, synthetic_mf=f"SYNTHETIC-MF-USR-{suffix}", sector=sector.strip()[:60],
                display_name=clean_name if clean_name.startswith("SYNTHÉTIQUE") else f"SYNTHÉTIQUE — {clean_name}",
                created_on=utcnow().date()))
        _materialize(self)
        return _admin_view(self, next(e for e in portfolio.enterprises() if e.company_id == company_id))

    def admin_delete_enterprise(self, actor: Actor, company_id: str, confirm: str) -> AdminPortfolioResult:
        """Delete one synthetic portfolio enterprise and its demo case. The curated case
        and any company outside the synthetic portfolio can never be deleted here."""
        authorize(self.registry, actor, "admin_delete_enterprise")
        portfolio = _require_portfolio(self)
        from boussla.portfolio_runtime import SYNTHETIC_ID
        if not isinstance(company_id, str) or not SYNTHETIC_ID.fullmatch(company_id) or not portfolio.is_member(company_id):
            raise BousslaError(ErrorCode.NOT_FOUND, "Entreprise synthétique inconnue")
        if confirm != company_id:
            raise BousslaError(ErrorCode.INVALID_INPUT, "Confirmation par l'identifiant requise", fields=["confirm"])
        _drop_enterprise_case(self, company_id)
        portfolio.delete(company_id)
        return AdminPortfolioResult(action="DELETE", enterprise_count=len(portfolio.enterprises()),
                                    case_ids=(portfolio.case_id(company_id),))



@dataclass(frozen=True)
class Evaluation:
    """Deterministic analysis of one case version (derived, never stored as fact)."""

    version: int
    findings: tuple[Finding, ...]
    hypotheses: tuple[Hypothesis, ...]
    scenarios: tuple[Scenario, ...]
    score: ScoreSnapshot


class BousslaAppService(_DemoAdministration):
    mode = Mode.LIVE

    def __init__(self, store: CaseStore, registry: ActorRegistry | None = None, checks=None,
                 settings: Settings | None = None, field_extractor=None, text_extractor=None,
                 integrity_inspector=None, document_router=None, reference_assistant=None,
                 context_assistant=None, history_signal_provider=None, investigator=None, clock=None,
                 portfolio=None) -> None:
        self.store = store
        # Read-time clock for demo deadlines/triage only (tests inject a fixed clock).
        self.clock = clock or utcnow
        # Optional lane B history signals and lane C investigator brief (officer-only,
        # guarded, never inputs to checks, scores, acceptance or revisions).
        self.investigator = investigator
        self._brief_cache: dict[tuple, tuple] = {}
        self._brief_questions: dict[str, tuple[str, ...]] = {}
        # Lane B synthetic operational portfolio (PortfolioRuntime): identities join the
        # enterprise registry and it is the default history-signal provider.
        self.portfolio = portfolio
        self.history_signal_provider = history_signal_provider or portfolio
        self.registry = registry or ActorRegistry.demo()
        self.checks = checks or get_checks_engine()
        # Hypothesis tests: lane B's if provided, else the labelled interim playbook tests.
        self._hypothesis_engine = self.checks if hasattr(self.checks, "test_hypotheses") else InterimChecks()
        self.settings = settings or get_settings()
        self.enterprises = load_enterprises()
        if portfolio is not None:
            self.enterprises.update({e.company_id: e for e in portfolio.enterprises()})
        self.text_extractor = text_extractor
        self.field_extractor = field_extractor
        self.integrity_inspector = integrity_inspector
        self.document_router = document_router
        # Lane C officer reference assistant (retrieval + optional grounded note), built
        # once per service/process. Enrichment runs AFTER deterministic evaluation and
        # never feeds findings, hypotheses, scores, acceptance or revisions.
        self.reference_assistant = reference_assistant
        generator = getattr(reference_assistant, "generator", None)
        if generator is not None and not isinstance(generator, _GuardedNoteGenerator):
            reference_assistant.generator = _GuardedNoteGenerator(generator)
        self._reference_cache: dict[tuple, tuple] = {}
        # Lane C project-context consistency (auxiliary; clarification only, never scoring).
        self.context_assistant = context_assistant
        interpreter = getattr(context_assistant, "interpreter", None)
        if interpreter is not None and not isinstance(interpreter, _GuardedInterpreter):
            context_assistant.interpreter = _GuardedInterpreter(interpreter)
        self._context_cache: dict[tuple, tuple] = {}

    # ================================================================ helpers
    def _open(self, actor: Actor, case_id: str, action: str) -> tuple[Actor, dict]:
        meta = self.store.case_meta(case_id)
        trusted = authorize(self.registry, actor, action, meta["company_id"], case_id)
        return trusted, meta

    @staticmethod
    def _input_hash(actor: Actor, action: str, payload: object) -> str:
        return stable_hash([actor.actor_id, action, payload])

    def _facts(self, case_id: str, version: int | None = None) -> dict[str, list]:
        s, v = self.store, version
        return {
            "transaction": s.facts(case_id, "transaction", Transaction, v),
            "invoice_observation": s.facts(case_id, "invoice_observation", InvoiceObservation, v),
            "payment": s.facts(case_id, "payment", Payment, v),
            "payment_allocation": s.facts(case_id, "payment_allocation", PaymentAllocation, v),
            "identity_mapping": s.facts(case_id, "identity_mapping", IdentityMapping, v),
            "allocation": s.facts(case_id, "allocation", Allocation, v),
            "quantity_reference": s.facts(case_id, "quantity_reference", QuantityReference, v),
            "context_claim": s.facts(case_id, "context_claim", ContextClaim, v),
            "delivery": s.facts(case_id, "delivery", Delivery, v),
            "settlement_adjustment": s.facts(case_id, "settlement_adjustment", SettlementAdjustment, v),
            "document": s.facts(case_id, "document", Document, v),
            "project": s.facts(case_id, "project", Project, v),
            "request": s.facts(case_id, "request", RequestView, v),
            "response": s.facts(case_id, "response", ClarificationResponse, v),
            "proposal": s.facts(case_id, "proposal", EvidenceProposal, v),
            "extraction": s.facts(case_id, "extraction", ExtractionProposal, v),
            "integrity": s.facts(case_id, "integrity", IntegrityReport, v),
            "routing": s.facts(case_id, "routing", RouterResult, v),
            "document_analysis": s.facts(case_id, "document_analysis", DocumentAnalysisReport, v),
        }

    def _clarification_status(self, requests: list[RequestView]) -> ClarificationStatus:
        """Administrative status only; never an input to the review index."""
        statuses = [r.request.status for r in requests]
        if not statuses:
            return ClarificationStatus.NOT_REQUESTED
        if any(d.overdue for d in clarification_deadlines(requests, self.clock())):
            return ClarificationStatus.FOLLOW_UP_DUE  # demo target passed; administrative only
        if RequestStatus.PUBLISHED_IN_DEMO in statuses:
            return ClarificationStatus.PENDING
        if RequestStatus.EXTENDED in statuses:
            return ClarificationStatus.EXTENSION_REQUESTED
        if RequestStatus.RESPONDED in statuses:
            return ClarificationStatus.ANSWERED
        return ClarificationStatus.CLOSED

    def _evaluate(self, case_id: str, company_id: str, version: int, facts: dict[str, list],
                  previous_snapshot: ScoreSnapshot | None = None,
                  as_of: datetime | None = None) -> Evaluation:
        recorded = next((r for r in self.store.revisions(case_id) if r.version == version), None)
        effective_as_of = as_of or (recorded.score_snapshot.cutoff if recorded and recorded.score_snapshot
                                    else recorded.created_at if recorded else self.clock())
        findings: list[Finding] = []
        hypotheses: list[Hypothesis] = []
        scenarios: list[Scenario] = []
        tx_scores = []
        pending = any(p.status is ProposalStatus.AWAITING_HUMAN_REVIEW for p in facts["proposal"])
        for tx in facts["transaction"]:
            inputs = TransactionInputs(
                case_id=case_id, company_id=company_id, case_version=version, as_of=effective_as_of, transaction=tx,
                invoice_observations=tuple(o for o in facts["invoice_observation"] if o.transaction_id == tx.transaction_id),
                payments=tuple(facts["payment"]), payment_allocations=tuple(facts["payment_allocation"]),
                settlement_adjustments=tuple(a for a in facts.get("settlement_adjustment", ())
                                             if a.transaction_id == tx.transaction_id),
                identity_mappings=tuple(facts["identity_mapping"]),
                allocations=tuple(a for a in facts["allocation"] if a.transaction_id == tx.transaction_id),
                quantity_references=tuple(facts["quantity_reference"]),
                context_claims=tuple(c for c in facts["context_claim"] if c.transaction_id in (None, tx.transaction_id)),
                deliveries=tuple(d for d in facts["delivery"] if d.transaction_id == tx.transaction_id),
                documents=tuple(facts["document"]))
            tx_findings = self.checks.evaluate_transaction(inputs)
            findings += tx_findings
            tx_scores.append(self.checks.score_transaction(tx_findings, set(ALL_FAMILIES)))
            scenarios += self.checks.run_scenarios(inputs, {})
            hypotheses += self._hypothesis_engine.test_hypotheses(inputs, tx_findings, pending_second_package=pending)
        raw_index = self.checks.aggregate_company(tx_scores)
        if previous_snapshot is None:
            previous_snapshot = next((revision.score_snapshot for revision in reversed(self.store.revisions(case_id))
                                      if revision.version <= version and revision.score_snapshot is not None), None)
        cause_progress = calculate_progress(tuple(findings),
                                            derive_progress_evidence(tuple(findings), facts, previous_snapshot))
        adjusted = [(transaction_progress_index(cause_progress, s.transaction_id)
                     if any(c.transaction_id == s.transaction_id for c in cause_progress) else s.review_index,
                     s.transaction_id) for s in tx_scores]
        scored = [(index, tx_id) for index, tx_id in adjusted if index is not None]
        index, decisive_transaction_id = max(scored, key=lambda pair: (pair[0], pair[1])) if scored else (None, None)
        evaluable = [s for s in tx_scores if s.evidence_coverage is not None]
        coverage = min((Decimal(s.evidence_coverage) for s in evaluable), default=None)
        unresolved_tx = {f.transaction_id for f in findings if f.status is FindingStatus.UNRESOLVED}
        contributions: dict[str, str] = {}
        for s in tx_scores:
            for fam, val in s.contributions.items():
                contributions[fam] = str(max(Decimal(val), Decimal(contributions.get(fam, "0"))))
        score = ScoreSnapshot(
            company_id=company_id, case_version=version, cutoff=effective_as_of,
            calculated_at=effective_as_of, engine_version=RULE_VERSION,
            cause_ids=tuple(c.cause_id for c in cause_progress),
            method_id="PROGRESSIVE_REVIEW_V2", rules_version="+".join(sorted({f.calculation_version for f in findings} | {RULE_VERSION})),
            review_index=index, raw_review_index=raw_index, cause_progress=cause_progress,
            decisive_transaction_id=decisive_transaction_id,
            evidence_coverage=str(coverage.quantize(Decimal("0.01"))) if coverage is not None else None,
            coverage_complete=bool(tx_scores) and all(s.coverage_complete for s in tx_scores),
            contributions=contributions,
            tested_families=tuple(sorted({f for s in tx_scores for f in s.evaluable_families}, key=lambda f: f.value)),
            unknown_families=tuple(sorted({f for s in tx_scores for f in s.unknown_families}, key=lambda f: f.value)),
            scope_note=f"Transactions du dossier {case_id} uniquement ; indice de priorité de revue, pas une probabilité de fraude.",
            unresolved_distinct_transactions=len(unresolved_tx),
            clarification_status=self._clarification_status(facts["request"]))
        return Evaluation(version, tuple(findings), tuple(hypotheses), tuple(scenarios), score)

    def evaluate(self, case_id: str, version: int | None = None) -> Evaluation:
        """Deterministic evaluation of a case version (used by the workflow graph)."""
        meta = self.store.case_meta(case_id)
        v = version or meta["version"]
        result = self._evaluate(case_id, meta["company_id"], v, self._facts(case_id, v))
        if version is not None:
            recorded = next((r.score_snapshot for r in self.store.revisions(case_id)
                             if r.version == version and r.score_snapshot is not None), None)
            if recorded is not None:
                return Evaluation(result.version, result.findings, result.hypotheses, result.scenarios, recorded)
        return result

    def _summaries(self, facts: dict[str, list]) -> tuple[TransactionSummary, ...]:
        out = []
        payments = {p.payment_id: p for p in facts["payment"]}
        for tx in facts["transaction"]:
            obs = [o for o in facts["invoice_observation"] if o.transaction_id == tx.transaction_id]
            primary = next((o for o in obs if o.perspective is Perspective.BUYER_RECEIVED), obs[0] if obs else None)
            settled = sum(pa.allocated_millimes for pa in facts["payment_allocation"]
                          if pa.transaction_id == tx.transaction_id
                          and payments.get(pa.payment_id) and payments[pa.payment_id].status is PaymentStatus.SETTLED)
            origins = {o.origin_group_id for o in obs}
            seller = self.enterprises.get(tx.seller_company_id or "")
            out.append(TransactionSummary(
                transaction_id=tx.transaction_id, counterparty_company_id=tx.seller_company_id,
                counterparty_display_name=seller.display_name if seller else None,
                invoice_number=primary.invoice_number if primary else None,
                issued_on=primary.issued_on if primary else None,
                invoiced_gross_millimes=primary.gross_millimes if primary else None,
                settled_millimes=settled if any(pa.transaction_id == tx.transaction_id for pa in facts["payment_allocation"]) else None,
                observation_perspectives=tuple(o.perspective for o in obs),
                corroboration_status=("DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY" if len(origins) > 1
                                      else "COMMON_ORIGIN" if len(obs) > 1 else "SINGLE_OBSERVATION"),
                project_id=tx.project_id))
        return tuple(out)

    def _doc_views(self, facts: dict[str, list], version: int) -> tuple[DocumentView, ...]:
        extractions = {e.document_id: e for e in facts["extraction"]}
        integrity = {i.document_id: i for i in facts["integrity"]}
        routing = {r.document_id: r for r in facts["routing"]}
        analyses = {r.document_id: r for r in facts.get("document_analysis", ())}
        return tuple(DocumentView(document=d, analysis=analyses.get(d.document_id),
                                  processing_status="ANALYZED_AWAITING_REVIEW" if d.document_id in analyses else "NOT_ANALYZED", extraction=extractions.get(d.document_id),
                                  integrity=integrity.get(d.document_id) or IntegrityReport(
                                      document_id=d.document_id, sha256=d.sha256,
                                      limitations=("INTEGRITY_ADAPTER_NOT_RUN",)),
                                  routing=routing.get(d.document_id),
                                  case_version=version, mode=Mode.LIVE) for d in facts["document"])

    @staticmethod
    def _router_mode(facts: dict[str, list]) -> Mode:
        """LIVE if any stored routing came from Jev, MANUAL if only fallbacks, else NOT_RUN."""
        modes = {r.mode for r in facts["routing"]}
        return Mode.LIVE if Mode.LIVE in modes else Mode.MANUAL if modes else Mode.NOT_RUN

    def _company_name(self, company_id: str) -> str:
        e = self.enterprises.get(company_id)
        return e.display_name if e else company_id

    # ================================================================== reads
    def get_case(self, actor: Actor, case_id: str) -> CompanyCaseView | OfficerCaseView:
        actor, meta = self._open(actor, case_id, "get_case")
        v, company = meta["version"], meta["company_id"]
        facts = self._facts(case_id, v)
        if actor.role is Role.COMPANY:
            published = tuple(r for r in facts["request"] if r.request.status is not RequestStatus.DRAFT)
            open_q = tuple(q for r in published if r.request.status is RequestStatus.PUBLISHED_IN_DEMO for q in r.questions)
            return CompanyCaseView(
                case_id=case_id, company_id=company, company_display_name=self._company_name(company), case_version=v,
                documents=tuple(dv.model_copy(update={"analysis": None}) for dv in self._doc_views(facts, v)
                                if dv.document.acquisition_channel.value != "SIMULATED_COUNTERPARTY_REFERENCE"),
                transactions=self._summaries(facts),
                projects=tuple(p for p in facts["project"] if p.company_id == company),
                context_claims=tuple(c for c in facts["context_claim"] if c.company_id == company),
                allocations=tuple(facts["allocation"]),
                pending_transcriptions=tuple(e for e in facts["extraction"] if e.status == "PROPOSED"),
                open_questions=open_q, inbox=self._decorated_requests(published),
                responses=tuple(r for r in facts["response"] if r.author_actor_id == actor.actor_id),
                context_assessment=self._context_assessment(case_id, company, v, facts)[0],
                mode=Mode.LIVE, banner_fr=DEMO_BANNER_FR)
        ev = self._evaluate(case_id, company, v, facts)
        raw_transaction_indices = {
            transaction.transaction_id: self.checks.score_transaction(
                [finding for finding in ev.findings if finding.transaction_id == transaction.transaction_id],
                set(ALL_FAMILIES)).review_index
            for transaction in facts["transaction"]
        }
        impact = tuple(ResolutionImpact.model_validate(item) for item in
                       simulate_resolution(ev.score, raw_transaction_indices))
        scenarios = ev.scenarios + self._reallocation_scenarios(case_id, company, v, facts, ev)
        view = OfficerCaseView(
            case_id=case_id, company_id=company, company_display_name=self._company_name(company), case_version=v,
            documents=self._doc_views(facts, v), transactions=self._summaries(facts),
            invoice_observations=tuple(facts["invoice_observation"]), payments=tuple(facts["payment"]),
            projects=tuple(facts["project"]), context_claims=tuple(facts["context_claim"]),
            quantity_references=tuple(facts["quantity_reference"]), allocations=tuple(facts["allocation"]),
            findings=ev.findings, hypotheses=ev.hypotheses, scenarios=scenarios, score=ev.score,
            impact_if_resolved=impact,
            requests=self._decorated_requests(facts["request"]), responses=tuple(facts["response"]),
            proposals=tuple(facts["proposal"]), deliveries=tuple(facts["delivery"]),
            **self._enterprise_360(company, facts),
            mode=Mode.LIVE, mode_by_node={"checks": Mode.LIVE, "retrieval": self._retrieval_mode(),
                                          "router": self._router_mode(facts)},
            banner_fr=DEMO_BANNER_FR)
        context_view, _, context_mode = self._context_assessment(case_id, company, v, facts)
        triage, deadlines, signals, history_mode = self._triage(case_id, company, v, ev, facts)
        historical = calculate_historical_indicator(signals)
        confidence_cutoff = self.clock()
        covered_ids = self._covered_history_transaction_ids(company, facts, confidence_cutoff)
        conflicted_ids = tuple(sorted({tx_id for signal in signals
                                      if signal.reason_code.value == "REPEATED_INVOICE_CONFLICT"
                                      for tx_id in signal.affected_transaction_ids}))
        confidence = calculate_operational_confidence(view.requests, view.responses, view.proposals,
                                                      signals, confidence_cutoff,
                                                      derive_progress_evidence(ev.findings, facts, None),
                                                      covered_ids, conflicted_ids)
        view = view.model_copy(update={"context_assessment": context_view, "triage": triage,
                                       "clarification_deadlines": deadlines, "history_signals": signals,
                                       "history_signal_index": historical.index,
                                       "history_signal_status": historical.status,
                                       "history_signal_factors": historical.factors,
                                       "history_signal_method": historical.method,
                                       "operational_confidence_index": confidence.index,
                                       "operational_confidence_status": confidence.status,
                                       "operational_confidence_as_of": confidence.as_of,
                                       "operational_confidence_factors": confidence.factors,
                                       "operational_confidence_eligible_observations": confidence.eligible_observations,
                                       "operational_confidence_method": confidence.method,
                                       "operational_confidence_sample_size": confidence.sample_size,
                                       "operational_confidence_data_quality": confidence.data_quality,
                                       "operational_confidence_sample_note_fr": confidence.sample_note_fr,
                                       "operational_confidence_window_start": confidence.window_start,
                                       "mode_by_node": {**view.mode_by_node, "context": context_mode,
                                                        "history": history_mode}})
        from boussla.behavior_profile import build_behavior_profile
        profile_cutoff = self.clock()
        coverage = {}
        if self.portfolio is not None and self.portfolio.is_member(company):
            profile_cutoff = min(profile_cutoff, self.portfolio.as_of)
            bundle = self.portfolio.bundle(company)
            coverage = {row["period"]: row["source_id"] for row in bundle["coverage"]} if bundle else {}
        profile_findings = (ev.findings if ev.score.cutoff == profile_cutoff else
                            self._evaluate(case_id, company, v, facts, as_of=profile_cutoff).findings)
        view = view.model_copy(update={"behavior_profile": build_behavior_profile(
            facts, coverage, profile_cutoff, self.store.events(case_id), profile_findings)})
        from boussla.indicators import case_indicators
        view = view.model_copy(update={"indicators": case_indicators(view, self.clock())})
        view = self._enrich_with_references(view, as_of=ev.score.cutoff.date())
        from boussla.actions import recommend_actions
        view = view.model_copy(update={"recommended_actions": recommend_actions(view)})
        return self._with_investigator_brief(view, facts)

    def _covered_history_transaction_ids(self, company_id: str, facts: dict[str, list],
                                         as_of: datetime) -> tuple[str, ...]:
        if self.portfolio is None or not self.portfolio.is_member(company_id):
            return ()
        bundle = self.portfolio.bundle(company_id)
        if bundle is None:
            return ()
        periods = {row["period"] for row in bundle["coverage"]
                   if row.get("source_id") and confidence_window_start(as_of).strftime("%Y-%m") <= row["period"] < as_of.strftime("%Y-%m")}
        buyer_tx = {o.transaction_id for o in facts["invoice_observation"]
                    if o.perspective is Perspective.BUYER_RECEIVED and o.available_at <= as_of
                    and o.issued_on >= confidence_window_start(as_of).date()}
        return tuple(sorted(t.transaction_id for t in facts["transaction"]
                            if t.economic_period in periods and t.transaction_id in buyer_tx))

    # ------------------------------------------------------- triage (queue urgency)
    def _history_signals(self, company_id: str, now: datetime):
        """Lane B history signals for this company; any failure is ignored (mode ERROR)."""
        if self.history_signal_provider is None or (
                self.history_signal_provider is self.portfolio and not self.portfolio.is_member(company_id)):
            return (), Mode.NOT_RUN  # no synthetic history for this company
        try:
            raw = self.history_signal_provider.signals(company_id, now.date())
            signals = tuple(s for s in raw if isinstance(s, CompanyHistorySignal) and s.company_id == company_id)
        except Exception:  # noqa: BLE001 - optional signal source, never fatal or a finding
            return (), Mode.ERROR
        return signals, Mode.LIVE

    def _triage(self, case_id: str, company_id: str, version: int, ev: Evaluation, facts: dict[str, list]):
        """(TriageAssessment, deadlines, history signals, history mode). Read-time only:
        never stored, never an input to the review index."""
        now = self.clock()
        signals, history_mode = self._history_signals(company_id, now)
        deadlines = clarification_deadlines(facts["request"], now)
        # Provisional score reductions do not de-prioritize an officer's pending decision.
        # The triage base is the visible raw documentary contribution, not history or AI.
        triage = assess_triage(case_id=case_id, case_version=version, review_index=ev.score.raw_review_index,
                               findings=ev.findings, deadlines=deadlines, proposals=facts["proposal"],
                               history_signals=signals, now=now)
        return triage, deadlines, signals, history_mode

    # ------------------------------------------------------- lane C investigator
    def _with_investigator_brief(self, view: OfficerCaseView, facts: dict[str, list]) -> OfficerCaseView:
        """Officer-only assisted analysis (lane C) after checks, history, context and retrieval.
        Cached per case version + history/reference fingerprints; any failure leaves the
        view unchanged (mode ERROR). Never feeds findings, scores, requests or revisions."""
        if self.investigator is None:
            return view.model_copy(update={"mode_by_node": {**view.mode_by_node, "investigator": Mode.NOT_RUN}})
        key = (view.case_id, view.case_version, tuple(sorted(s.signal_id for s in view.history_signals)),
               tuple(sorted(p.rule_id for p in view.candidate_passages)))
        cached = self._brief_cache.get(key)
        if cached is None:
            with traced("investigator", view.case_id, case_version=view.case_version) as meta:
                cached = self._compute_brief(view, facts)
                meta.update(mode=(cached[0].mode if cached[0] else cached[1] or Mode.NOT_RUN).value,
                            question_count=len(cached[0].questions_proposed) if cached[0] else 0)
            if len(self._brief_cache) > 256:
                self._brief_cache.clear()
            self._brief_cache[key] = cached
        brief, error = cached
        if brief is not None:
            self._brief_questions[view.case_id] = brief.questions_proposed
        return view.model_copy(update={"investigator_brief": brief, "mode_by_node": {
            **view.mode_by_node, "investigator": error or (brief.mode if brief else Mode.NOT_RUN)}})

    def _compute_brief(self, view: OfficerCaseView, facts: dict[str, list]) -> tuple:
        """(brief | None, error mode | None); a model failure falls back to the template brief."""
        try:
            return self._investigator_brief(view, facts, self.investigator), None
        except Exception:  # noqa: BLE001 - model/selector failure: deterministic template brief
            try:
                from boussla.investigator import InvestigatorAssistant
                return self._investigator_brief(view, facts, InvestigatorAssistant()), None
            except Exception:  # noqa: BLE001 - assistive layer; never fatal, never a finding
                return None, Mode.ERROR

    def _investigator_brief(self, view: OfficerCaseView, facts: dict[str, list],
                            assistant) -> InvestigatorBriefView | None:
        from boussla.investigator import (
            HYPOTHESIS_CATALOGUE, ClarificationDigest, ContextDigest, EvidenceFeature, FindingDigest,
            InvestigatorInput, ScenarioDigest,
        )
        from boussla.investigator.models import _CODE

        aliases: dict[str, str] = {}

        def code(ref: str) -> str:  # opaque, bounded reference codes only (no long numeric IDs)
            return ref if _CODE.fullmatch(ref) else aliases.setdefault(ref, f"REF-{chr(65 + len(aliases) % 26)}"
                                                                           f"{len(aliases) // 26 or ''}")

        def codes(values, limit=10) -> tuple[str, ...]:
            return tuple(dict.fromkeys(code(v) for v in values if v))[:limit]

        # Only findings that still need an explanation reach the investigator.
        order = {FindingStatus.UNRESOLVED: 0, FindingStatus.INSUFFICIENT: 1}
        ranked = sorted((f for f in view.findings if f.status in order),
                        key=lambda f: (order[f.status], f.finding_id))[:12]
        findings = tuple(FindingDigest(
            family=f.family, reason_code=code(f.reason_code or "UNSPECIFIED"), status=f.status,
            evidence_refs=codes(r.document_id or r.source_record_id for r in f.evidence_refs),
            missing_evidence=codes(f.missing_evidence_types, 5),
            coverage_code="COMPLETE" if view.score and view.score.coverage_complete else "INCOMPLETE") for f in ranked)
        known_refs = {r for f in findings for r in f.evidence_refs}
        features = []
        for h in view.hypotheses:
            target = PLAYBOOK_TO_CATALOGUE.get(h.statement_template_id)
            if target is None or any(ft.hypothesis_id == target for ft in features):
                continue
            features.append(EvidenceFeature(
                hypothesis_id=target,
                supporting_refs=tuple(r for r in codes(x.document_id or x.source_record_id for x in h.supporting_refs)
                                      if r in known_refs),
                contradicting_refs=tuple(r for r in codes(x.document_id or x.source_record_id
                                                          for x in h.contradicting_refs) if r in known_refs),
                missing_evidence=codes(h.missing_evidence_types, 5)))
        ctx = view.context_assessment
        context = None if ctx is None else ContextDigest(
            declared_purpose_code=ctx.declared_purpose_category.value, declared_horizon_code=ctx.declared_horizon.value,
            interpreted_horizon_code=ctx.interpreted_horizon.value if ctx.interpretation_mode is Mode.LIVE else "UNKNOWN",
            consistency_code=ctx.consistency_status, reason_codes=tuple(ctx.reason_codes)[:10])
        answered = sorted(self._answered_question_ids(facts) | {q for r in facts["response"] for q in r.answers})
        choice_answers = sorted({a.strip() for r in facts["response"] for a in r.answers.values()
                                 if a.strip() in HorizonBucket.__members__ or a.strip() in PurposeCategory.__members__})
        history_codes = tuple(dict.fromkeys(s.reason_code.value for s in view.history_signals))
        rule_ids = tuple(dict.fromkeys(p.rule_id for p in view.candidate_passages if _CODE.fullmatch(p.rule_id)))[:10]
        scenario_digests = []
        for n, sc in enumerate(view.scenarios[:5], 1):
            idx = sc.outputs.get("hypothetical_review_index")
            outcome = ("RESOLVES_IN_SIMULATION" if idx == "0" else "RESIDUAL_IN_SIMULATION" if idx is not None
                       else "RESIDUAL_UNITS_REPORTED" if sc.outputs.get("residual_units") else "NOT_INDEXED")
            scenario_digests.append(ScenarioDigest(f"SCENARIO-{n}", outcome,
                                                   int(idx) if idx is not None and idx.isdigit() else None))
        data = InvestigatorInput(
            findings=findings, evidence_features=tuple(features[:10]), context=context,
            history_signal_codes=history_codes[:10],
            transaction_summary_codes=tuple(dict.fromkeys(t.corroboration_status for t in view.transactions
                                                          if _CODE.fullmatch(t.corroboration_status)))[:5],
            clarification=ClarificationDigest(
                status=view.score.clarification_status if view.score else ClarificationStatus.NOT_REQUESTED,
                answered_question_ids=tuple(q for q in answered if q in QUESTIONS)[:10],
                answer_codes=tuple(choice_answers)[:10]),
            reference_rule_ids=rule_ids, scenarios=tuple(scenario_digests))
        result = assistant.assess(data, audience=Audience.OFFICER)
        brief = result.brief
        if brief is None:
            return None
        # Authority boundary: only catalogue hypotheses, allowlisted questions, retrieved rules
        # and known history codes survive; anything else invalidates the brief.
        if (len(brief.top_hypotheses) > 5
                or any(h.hypothesis_id not in HYPOTHESIS_CATALOGUE for h in brief.top_hypotheses)
                or any(q not in QUESTIONS for q in brief.suggested_question_ids)
                or not set(brief.reference_rule_ids) <= {p.rule_id for p in view.candidate_passages}):
            raise BousslaError(ErrorCode.MODEL_UNAVAILABLE, "Analyse assistée invalide")
        asked = tuple(dict.fromkeys(q for r in facts["request"] if r.request.status is not RequestStatus.DRAFT
                                    for q in r.request.question_ids))
        observations = [BriefObservationView(kind=o.kind.value, text_fr=o.text_fr, source_codes=tuple(o.source_codes))
                        for o in brief.key_observations]
        observations += [BriefObservationView(
            kind="FACT", text_fr=f"Historique synthétique observé ({s.period}) : {s.explanation_fr}",
            source_codes=(s.reason_code.value,)) for s in view.history_signals if s.reason_code in ANOMALY_CODES][:5]
        return InvestigatorBriefView(
            case_id=view.case_id, case_version=view.case_version, summary_fr=brief.summary_fr,
            key_observations=tuple(observations),
            top_hypotheses=tuple(BriefHypothesisView(
                hypothesis_id=h.hypothesis_id, name_fr=HYPOTHESIS_NAMES_FR[h.hypothesis_id], status=h.status.value,
                supporting_refs=h.supporting_refs, contradicting_refs=h.contradicting_refs,
                missing_evidence=h.missing_evidence, why_it_matters_fr=h.why_it_matters_fr)
                for h in brief.top_hypotheses[:5]),
            missing_information=tuple(brief.missing_information),
            changes_since_previous_version=self._changes_since_previous(view),
            questions_proposed=tuple(q for q in brief.suggested_question_ids if q not in asked)[:MAX_QUESTIONS_PER_ROUND],
            questions_already_asked=asked, reference_rule_ids=tuple(brief.reference_rule_ids),
            history_signal_codes=history_codes, limitations=tuple(brief.limitations), mode=brief.mode)

    def _changes_since_previous(self, view: OfficerCaseView) -> tuple[str, ...]:
        """Deterministic finding-status differences between this and the previous version."""
        if view.case_version <= 1:
            return ("Première version du dossier.",)
        previous = self._evaluate(view.case_id, view.company_id, view.case_version - 1,
                                  self._facts(view.case_id, view.case_version - 1))
        before = {(f.transaction_id, f.family): f for f in previous.findings}
        out = [f"{f.family.value} {f.transaction_id} : {before[(f.transaction_id, f.family)].status.value} → "
               f"{f.status.value}" for f in view.findings
               if (f.transaction_id, f.family) in before and before[(f.transaction_id, f.family)].status is not f.status]
        if previous.score.review_index != (view.score.review_index if view.score else None):
            out.append(f"Indice de revue : {previous.score.review_index} → {view.score.review_index}")
        revision = next((r for r in self.store.revisions(view.case_id) if r.version == view.case_version), None)
        if revision is not None:
            out.append(f"Dernière révision : {revision.reason}")
        return tuple(out) or ("Aucun changement de constat depuis la version précédente.",)

    # ------------------------------------------------------- enterprise 360 (officer)
    def _enterprise_360(self, company_id: str, facts: dict[str, list]) -> dict:
        e = self.enterprises.get(company_id)
        bundle = self.portfolio.bundle(company_id) if self.portfolio is not None else None
        months: dict[str, dict] = {}
        for tx in facts["transaction"]:
            m = months.setdefault(tx.economic_period, {"tx": 0, "inv": 0, "out": 0})
            m["tx"] += 1
            m["inv"] += sum(o.transaction_id == tx.transaction_id for o in facts["invoice_observation"])
        tx_of_payment = {a.payment_id: a.transaction_id for a in facts["payment_allocation"]}
        for pay in facts["payment"]:
            if pay.status is PaymentStatus.SETTLED:
                months.setdefault(pay.occurred_at.strftime("%Y-%m"), {"tx": 0, "inv": 0, "out": 0})["out"] += \
                    pay.amount_millimes
        periods = sorted(months)
        coverage = ({row["period"]: row["source_id"] for row in bundle["coverage"]}
                    if bundle is not None else {})
        monthly_context = build_monthly_context(
            {period: (value["tx"], value["inv"], value["out"]) for period, value in months.items()},
            coverage, bundle["history_end"] if bundle is not None else self.clock().strftime("%Y-%m"))
        profile = None if e is None else EnterpriseProfileView(
            company_id=company_id, display_name=e.display_name, synthetic_identifier=e.synthetic_mf, sector=e.sector,
            created_on=e.created_on, portfolio_member=bundle is not None,
            activity_start=bundle["history_start"] if bundle else (periods[0] if periods else None),
            activity_end=bundle["history_end"] if bundle else (periods[-1] if periods else None))
        return {
            "enterprise_profile": profile,
            "monthly_activity": monthly_context,
            "payment_timeline": tuple(PaymentTimelineEntry(
                payment_id=pay.payment_id, transaction_id=tx_of_payment.get(pay.payment_id), occurred_at=pay.occurred_at,
                amount_millimes=pay.amount_millimes, currency=pay.currency, status=pay.status,
                origin_group_id=pay.origin_group_id) for pay in sorted(facts["payment"], key=lambda x: x.occurred_at)),
            "financial_snapshot": self.portfolio.financial_snapshot(company_id) if self.portfolio is not None else None,
            "invoice_comparisons": self._invoice_comparisons(facts),
        }

    def _invoice_comparisons(self, facts: dict[str, list]) -> tuple[InvoiceComparisonView, ...]:
        from boussla.reconciliation import compare_transaction
        cutoff = self.clock()
        result = []
        known_payments = {p.payment_id for p in facts["payment"] if p.available_at <= cutoff}
        for transaction in facts["transaction"]:
            comparison = compare_transaction(transaction, facts["invoice_observation"], facts["document"], cutoff)
            result.append(comparison.model_copy(update={
                "payment_ids": tuple(sorted({a.payment_id for a in facts["payment_allocation"]
                    if a.transaction_id == transaction.transaction_id and a.payment_id in known_payments
                    and a.accepted_at <= cutoff})),
                "delivery_ids": tuple(sorted(d.delivery_id for d in facts["delivery"]
                    if d.transaction_id == transaction.transaction_id and d.received_at <= cutoff.date())),
                "project_ids": tuple(sorted({a.target_project_id for a in facts["allocation"]
                    if a.transaction_id == transaction.transaction_id and a.target_project_id
                    and a.status is AllocationStatus.ACCEPTED and a.effective_on <= cutoff.date()}
                    | ({transaction.project_id} if transaction.project_id else set())))}))
        return tuple(result)

    # ------------------------------------------------------- deterministic scenarios
    def _reallocation_scenarios(self, case_id: str, company_id: str, version: int, facts: dict[str, list],
                                ev: Evaluation) -> tuple[Scenario, ...]:
        """Hypothetical reallocation of an over-allocated quantity to another of the
        company's projects with an unused quantity reference, evaluated by the SAME
        deterministic checks on a cloned, non-canonical fact set. Nothing is written."""
        out = []
        refs = [r for r in facts["quantity_reference"] if r.company_id == company_id]
        for f in ev.findings:
            if f.family is not FindingFamily.QUANTITY or f.status is not FindingStatus.UNRESOLVED:
                continue
            allocs = [a for a in facts["allocation"] if a.transaction_id == f.transaction_id
                      and a.status is AllocationStatus.ACCEPTED and a.target_project_id]
            line = next((ln for o in facts["invoice_observation"] if o.transaction_id == f.transaction_id
                         and o.perspective is Perspective.BUYER_RECEIVED for ln in o.lines), None)
            if line is None:
                continue

            def ref_qty(project_id):
                return sum((Decimal(r.quantity) for r in refs if r.project_id == project_id and r.unit == line.unit
                            and r.item_code in (line.normalized_item_code, None)), Decimal(0))

            for over in allocs:
                excess = Decimal(over.quantity) - ref_qty(over.target_project_id)
                if excess <= 0:
                    continue
                used = {a.target_project_id: Decimal(a.quantity) for a in allocs}
                for project in sorted({r.project_id for r in refs} - {over.target_project_id}):
                    headroom = ref_qty(project) - used.get(project, Decimal(0))
                    moved = min(excess, headroom)
                    if moved <= 0:
                        continue
                    kept = Decimal(over.quantity) - moved
                    clone = [a for a in facts["allocation"] if a.allocation_id != over.allocation_id]
                    clone += [over.model_copy(update={"quantity": str(kept)}), Allocation(
                        allocation_id=f"HYP-{over.allocation_id}-{project}", transaction_id=over.transaction_id,
                        line_id=over.line_id, target_project_id=project, target_type=AllocationTarget.PROJECT,
                        quantity=str(moved), unit=over.unit, effective_on=over.effective_on,
                        status=AllocationStatus.ACCEPTED, fact_kind="HYPOTHETICAL_SCENARIO")]
                    after = self._evaluate(case_id, company_id, version, {**facts, "allocation": clone})
                    qty_after = next((x for x in after.findings if x.transaction_id == f.transaction_id
                                      and x.family is FindingFamily.QUANTITY), None)
                    out.append(Scenario(
                        scenario_id=f"{f.transaction_id}:REALLOCATION:{project}:v{version}",
                        label=f"Réaffectation hypothétique {over.target_project_id}={kept} / {project}={moved}",
                        inputs={"from_project": over.target_project_id or "", "to_project": project,
                                "moved_quantity": str(moved), "unit": over.unit},
                        outputs={"status": "HYPOTHETICAL", "current_review_index": str(ev.score.review_index),
                                 "hypothetical_review_index": str(after.score.review_index),
                                 "quantity_status_after": qty_after.status.value if qty_after else "NOT_EVALUATED",
                                 "residual_units": qty_after.quantity_difference or "0" if qty_after else "",
                                 "unit": over.unit},
                        evidence_refs=f.evidence_refs))
        return tuple(out)

    # ------------------------------------------------------- clarification read model
    def _decorated_requests(self, requests) -> tuple[RequestView, ...]:
        """Read-time follow-up state (demo target vs clock) for requests awaiting a response."""
        now = self.clock()
        out = []
        for rv in requests:
            req = rv.request
            state = None
            if req.status in PENDING_STATUSES:
                overdue = req.target_response_at is not None and now > req.target_response_at
                state = "FOLLOW_UP_DUE" if overdue else "ON_TRACK"
            out.append(rv.model_copy(update={"request": req.model_copy(update={"overdue_state": state})}))
        return tuple(out)

    # ------------------------------------------------------- context consistency
    @staticmethod
    def _context_base_claim(company_id: str, facts: dict[str, list]):
        """Latest company-confirmed context declaration (answers to Q-* are separate claims)."""
        claims = [c for c in facts["context_claim"]
                  if c.company_id == company_id and not c.purpose_text.startswith("[Q-")]
        return max(claims, key=lambda c: (c.submitted_at, c.claim_id)) if claims else None

    def _context_assessment(self, case_id: str, company_id: str, version: int, facts: dict[str, list]):
        """(ContextAssessmentView | None, reason codes, interpretation mode). Auxiliary only:
        computed from the company's own declaration, never fed to checks or scores."""
        claim = self._context_base_claim(company_id, facts)
        if self.context_assistant is None or claim is None:
            return None, (), Mode.NOT_RUN
        answered = frozenset(self._answered_question_ids(facts))
        key = (case_id, version, claim.claim_id, answered)
        cached = self._context_cache.get(key)
        if cached is None:
            from boussla.contracts import ContextAssessmentView
            from boussla.context.models import ContextInput
            try:
                # reference_expected stays False: no trusted fact currently establishes that a
                # project/allocation reference is required for this declaration.
                context = ContextInput.from_claim(claim, declared_horizon=claim.declared_horizon,
                                                  project_reference=None, reference_expected=False)
                assessment = self.context_assistant.assess(context, answered_question_ids=answered)
            except Exception:  # noqa: BLE001 - auxiliary layer never blocks the case
                return None, (), Mode.ERROR
            c, i = assessment.consistency, assessment.interpretation
            view = ContextAssessmentView(
                claim_id=claim.claim_id, declared_horizon=c.declared_horizon,
                interpreted_horizon=c.interpreted_horizon, calculated_horizon=c.calculated_horizon,
                declared_purpose_category=c.declared_purpose_category,
                interpreted_purpose_category=c.interpreted_purpose_category,
                duration_days=c.duration_days, consistency_status=c.status.value,
                reason_codes=tuple(r.value for r in c.reason_codes),
                recommended_question_ids=tuple(assessment.recommended_question_ids),
                supporting_spans=tuple(sp for sp in i.supporting_spans if sp in claim.purpose_text),
                interpretation_mode=assessment.mode)
            cached = (view, view.reason_codes, assessment.mode)
            if len(self._context_cache) > 128:
                self._context_cache.clear()
            self._context_cache[key] = cached
        return cached

    # ------------------------------------------------------- reference enrichment
    def _retrieval_mode(self) -> Mode:
        backend = getattr(getattr(self.reference_assistant, "retriever", None), "backend_mode", "NOT_SUPPLIED")
        return {"QDRANT": Mode.LIVE, "LEXICAL": Mode.TEMPLATE}.get(backend, Mode.NOT_RUN)

    def _enrich_with_references(self, view: OfficerCaseView, *, as_of) -> OfficerCaseView:
        """Officer-only candidate passages + grounded note, computed from the already
        final view. ``as_of`` is the server-side evaluation cutoff, never user input.
        Any failure leaves the deterministic view unchanged (retrieval mode ERROR)."""
        if self.reference_assistant is None:
            return view
        from boussla.contracts import GroundedNoteView
        key = (view.case_id, view.case_version, as_of,
               tuple(sorted((f.family.value, f.reason_code or "") for f in view.findings)))
        cached = self._reference_cache.get(key)
        if cached is None:
            try:
                result = self.reference_assistant.for_findings(view.findings, as_of=as_of, audience=Audience.OFFICER)
            except Exception:  # noqa: BLE001 - enrichment failure never blocks the dossier
                return view.model_copy(update={"mode_by_node": {**view.mode_by_node, "retrieval": Mode.ERROR}})
            passages = tuple(result.candidate_passages)
            note = None
            allowed = {p.rule_id for p in passages}
            if result.grounded_note is not None and set(result.grounded_note.candidate_rule_ids) <= allowed:
                n = result.grounded_note
                note = GroundedNoteView(
                    summary_fr=n.summary_fr, candidate_rule_ids=tuple(n.candidate_rule_ids),
                    applicability_questions=tuple(n.applicability_questions), limitations=tuple(n.limitations),
                    provider_model=n.provider_model, generation_mode=result.generation_mode)
            cached = (passages, note, result.retrieval_mode, note.generation_mode if note else Mode.NOT_RUN)
            if len(self._reference_cache) > 64:
                self._reference_cache.clear()
            self._reference_cache[key] = cached
        passages, note, retrieval_mode, generation_mode = cached
        return view.model_copy(update={
            "candidate_passages": passages, "reference_note": note,
            "mode_by_node": {**view.mode_by_node, "retrieval": retrieval_mode, "reference_note": generation_mode},
        })

    def list_queue(self, actor: Actor, cutoff, limit: int, cursor: str | None = None) -> QueuePage:
        actor = authorize(self.registry, actor, "list_queue")
        items = []
        for meta in self.store.list_cases():
            if meta["case_id"] not in actor.assigned_case_ids:
                continue
            facts = self._facts(meta["case_id"], meta["version"])
            ev = self._evaluate(meta["case_id"], meta["company_id"], meta["version"], facts)
            triage, _, signals, _ = self._triage(meta["case_id"], meta["company_id"], meta["version"], ev, facts)
            historical = calculate_historical_indicator(signals)
            enterprise = self.enterprises.get(meta["company_id"])
            dates = [o.issued_on for o in facts["invoice_observation"]] + [p.occurred_at.date() for p in facts["payment"]]
            items.append(QueueItem(
                case_id=meta["case_id"], company_id=meta["company_id"],
                company_display_name=self._company_name(meta["company_id"]), case_version=meta["version"],
                review_index=ev.score.review_index, evidence_coverage=ev.score.evidence_coverage,
                coverage_complete=ev.score.coverage_complete,
                active_finding_count=sum(f.status is FindingStatus.UNRESOLVED for f in ev.findings),
                clarification_status=ev.score.clarification_status, scope_note=ev.score.scope_note,
                triage_priority=triage.triage_priority, triage_reason_codes=triage.reason_codes,
                sector=enterprise.sector if enterprise else None,
                synthetic_identifier=enterprise.synthetic_mf if enterprise else None,
                last_activity_at=max(dates) if dates else None,
                history_signal_codes=tuple(dict.fromkeys(x.reason_code.value for x in signals)),
                history_signal_index=historical.index,
                history_anomaly=any(x.reason_code in ANOMALY_CODES for x in signals) if signals else None))
        # Queue order = operational urgency first, then documentary review priority (null
        # last), then most recent activity, then case ID. React never computes an order.
        items.sort(key=lambda i: (-(i.triage_priority or 0),
                                  -(i.review_index if i.review_index is not None else -1),
                                  -(i.last_activity_at.toordinal() if i.last_activity_at else 0), i.case_id))
        try:
            start = int(cursor) if cursor else 0
        except ValueError:
            start = -1
        if start < 0:
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Curseur de pagination invalide")
        page = items[start:start + limit]
        nxt = str(start + limit) if start + limit < len(items) else None
        return QueuePage(items=tuple(page), next_cursor=nxt,
                         cutoff=cutoff if isinstance(cutoff, datetime) else utcnow(), mode=Mode.LIVE)

    def get_audit(self, actor: Actor, case_id: str) -> dict:
        self._open(actor, case_id, "get_audit")
        return {"case_id": case_id, "records": self.store.audit_records(case_id),
                "legacy_events_without_audit": max(0, len(self.store.events(case_id)) -
                                                   len(self.store.audit_records(case_id)))}

    def get_history(self, actor: Actor, case_id: str) -> HistoryView:
        actor, meta = self._open(actor, case_id, "get_history")
        company = actor.role is Role.COMPANY
        internal = {"ANALYSIS_OFFICER", "EVIDENCE_REJECTED", "EXPORT"}
        events = tuple(e for e in self.store.events(case_id) if not (company and e.kind in internal))
        revisions = tuple(r.model_copy(update={"score_snapshot": None}) if company else r
                          for r in self.store.revisions(case_id))
        if company:
            return HistoryView(case_id=case_id, audience=Audience.COMPANY,
                               revisions=revisions, events=events, mode=Mode.LIVE)
        now = self.clock()
        signals, _ = self._history_signals(meta["company_id"], now)
        changes = []
        previous = None
        previous_version = None
        for revision in revisions:
            current = self._confidence_at_version(case_id, meta["company_id"], revision.version,
                                                  revision.created_at, signals)
            if previous is not None:
                change = confidence_delta(previous, current, from_version=previous_version,
                                          to_version=revision.version)
                if change is not None:
                    changes.append(change)
            previous, previous_version = current, revision.version
        if previous is not None and revisions and now >= revisions[-1].created_at:
            current = self._confidence_at_version(case_id, meta["company_id"], revisions[-1].version,
                                                  now, signals)
            change = confidence_delta(previous, current, from_version=revisions[-1].version,
                                      to_version=revisions[-1].version)
            if change is not None:
                changes.append(change)
        return OfficerHistoryView(case_id=case_id, revisions=revisions, events=events,
                                  operational_confidence_changes=tuple(changes), mode=Mode.LIVE)

    def ask_investigation(self, actor: Actor, case_id: str, question: str) -> InvestigationAnswer:
        trusted, _ = self._open(actor, case_id, "ask_investigation")
        clean_question = question.strip()
        if not 3 <= len(clean_question) <= 500:
            raise BousslaError(ErrorCode.INVALID_INPUT, "Question attendue (3 à 500 caractères)")
        view = self.get_case(trusted, case_id)
        history = self.get_history(trusted, case_id)
        network = self.get_network(trusted, case_id=case_id)
        return answer_investigation(clean_question, view, history, network)

    def get_network(self, actor: Actor, *, company_id: str | None = None,
                    case_id: str | None = None) -> NetworkView:
        trusted = authorize(self.registry, actor, "get_network")
        available = {meta["case_id"]: meta for meta in self.store.list_cases()
                     if meta["case_id"] in trusted.assigned_case_ids}
        if case_id is not None and case_id not in available:
            raise BousslaError(ErrorCode.FORBIDDEN, "Dossier non assigné à cet agent")
        selected = []
        for current_id, meta in sorted(available.items()):
            if case_id is not None and current_id != case_id:
                continue
            facts = self._facts(current_id, meta["version"])
            if company_id is not None and not (
                meta["company_id"] == company_id or
                any(company_id in (tx.buyer_company_id, tx.seller_company_id) for tx in facts["transaction"]) or
                any(company_id in (obs.issuer_company_id, obs.buyer_company_id)
                    for obs in facts["invoice_observation"])):
                continue
            selected.append((current_id, facts))
        if company_id is not None and not selected:
            raise BousslaError(ErrorCode.NOT_FOUND, "Entreprise absente du réseau autorisé")
        return build_network(selected, names={key: value.display_name for key, value in self.enterprises.items()},
                             scope="CASE" if case_id is not None else "COMPANY" if company_id is not None else "ALL",
                             scope_id=case_id or company_id)

    def get_notifications(self, actor: Actor, case_id: str) -> dict:
        """Internal feed projected from durable events; RECORDED is not an unread claim."""
        history = self.get_history(actor, case_id)
        company = history.audience is Audience.COMPANY
        company_document_ids = ({view.document.document_id for view in self.get_case(actor, case_id).documents}
                                if company else set())
        company_titles = {
            "AUTO_CLARIFICATION_PUBLISHED": "Nouvelle demande",
            "REQUEST_PUBLISHED": "Nouvelle demande",
            "DOCUMENT_ANALYZED": "Document analysé",
            "TRANSCRIPTION_CONFIRMED": "Dossier mis à jour",
            "TRANSCRIPTION_CORRECTED": "Dossier mis à jour",
        }
        officer_titles = {
            "UPLOAD": "Document reçu", "DOCUMENT_ANALYZED": "Document à vérifier",
            "RESPONSE": "Réponse reçue", "TRANSCRIPTION_CONFIRMED": "Champs confirmés",
            "TRANSCRIPTION_CORRECTED": "Champs corrigés", "EVIDENCE_REJECTED": "Pièce rejetée",
            "EVIDENCE_ACCEPTED": "Pièce acceptée", "AUTO_CLARIFICATION_PUBLISHED": "Demande publiée",
            "REQUEST_PUBLISHED": "Demande publiée",
        }
        titles = company_titles if company else officer_titles
        items = []
        for event in history.events:
            title = titles.get(event.kind)
            if title is None:
                continue
            if company:
                if event.kind == "DOCUMENT_ANALYZED" and not set(event.fact_ids) & company_document_ids:
                    continue
                if event.kind.startswith("TRANSCRIPTION_") and event.actor_id != actor.actor_id:
                    continue
            items.append({"notification_id": event.event_id, "kind": event.kind, "title_fr": title,
                          "message_fr": event.summary, "occurred_at": event.at.isoformat(),
                          "case_version": event.case_version, "source_event_id": event.event_id,
                          "status": "RECORDED"})
        if not company:
            by_version = {revision.version: revision for revision in history.revisions}
            for revision in history.revisions:
                before = by_version.get(revision.parent_version) if revision.parent_version is not None else None
                if (before is None or before.score_snapshot is None or revision.score_snapshot is None
                        or before.score_snapshot.review_index == revision.score_snapshot.review_index):
                    continue
                items.append({"notification_id": f"SCORE-{case_id}-v{revision.version}",
                              "kind": "SCORE_CHANGED", "title_fr": "Indice de revue modifié",
                              "message_fr": (f"Indice de revue : {before.score_snapshot.review_index} → "
                                             f"{revision.score_snapshot.review_index}"),
                              "occurred_at": revision.created_at.isoformat(), "case_version": revision.version,
                              "source_event_id": None, "status": "RECORDED"})
        items.sort(key=lambda item: (item["occurred_at"], item["notification_id"]), reverse=True)
        return {"case_id": case_id, "audience": history.audience.value, "items": items[:100]}

    def _confidence_at_version(self, case_id: str, company_id: str, version: int,
                               as_of: datetime, signals: tuple[CompanyHistorySignal, ...]):
        facts = self._facts(case_id, version)
        evidence = ()
        if facts["response"]:
            ev = self._evaluate(case_id, company_id, version, facts, as_of=as_of)
            evidence = derive_progress_evidence(ev.findings, facts, None)
        scoped_signals = tuple(s for s in signals if s.period.split("/")[-1] < as_of.strftime("%Y-%m"))
        conflicted = tuple(sorted({tx_id for signal in scoped_signals
                                  if signal.reason_code.value == "REPEATED_INVOICE_CONFLICT"
                                  for tx_id in signal.affected_transaction_ids}))
        return calculate_operational_confidence(
            tuple(facts["request"]), tuple(facts["response"]), tuple(facts["proposal"]),
            scoped_signals, as_of, evidence,
            self._covered_history_transaction_ids(company_id, facts, as_of), conflicted)

    # ================================================================= writes
    def create_case(self, actor: Actor, company_id: str, project_payload: dict, request_id: str):
        trusted = authorize(self.registry, actor, "create_case")
        if trusted.role is Role.COMPANY and trusted.company_id != company_id:
            raise BousslaError(ErrorCode.CROSS_COMPANY, "Création pour une autre entreprise interdite")
        if company_id not in self.enterprises:
            raise BousslaError(ErrorCode.NOT_FOUND, "Entreprise inconnue")
        case_id = f"CASE-{uuid.uuid5(uuid.NAMESPACE_URL, f'{trusted.actor_id}:{request_id}').hex[:10].upper()}"
        if not self.store.case_exists(case_id):
            label = str(project_payload.get("label", "")).strip()[:120]
            if not label:
                raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Libellé de projet requis")
            project = _validated(Project, project_id=f"PRJ-{case_id[5:]}", company_id=company_id, label=label,
                              project_type=str(project_payload.get("project_type", "OTHER_OR_UNKNOWN")),
                              planned_start=project_payload.get("planned_start") or None,
                              planned_end=project_payload.get("planned_end") or None, status="DECLARED")
            with self.store.write(case_id) as tx:
                tx.create_case(company_id, "Création du dossier")
                tx.put("project", project.project_id, project)
                tx.commit_version("Création du dossier par l'entreprise")
                tx.event("CASE_CREATED", trusted.actor_id, "Dossier créé", (project.project_id,))
            for officer in [a for a in self.registry.actors.values() if a.role is Role.OFFICER]:
                self.registry.assign(officer.actor_id, case_id)  # demo: single local officer pool
        return self.get_case(trusted, case_id)

    def upload_document(self, actor: Actor, case_id: str, upload_bytes: bytes, filename: str, media_type: str,
                        expected_version: int, request_id: str, response_id: str | None = None) -> DocumentView:
        actor, meta = self._open(actor, case_id, "upload_document")
        safe_name = Path(filename).name[:120]
        digest = hashlib.sha256(upload_bytes).hexdigest()
        ihash = self._input_hash(actor, "upload_document", [safe_name, media_type, digest, expected_version, response_id])
        if response_id is not None:
            self._upload_response_scope(case_id, actor, response_id)
        # Validate before any processing of arbitrary content.
        if len(upload_bytes) > self.settings.max_upload_bytes:
            raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier trop volumineux (10 Mo max.)")
        if media_type != "application/pdf" or not safe_name.lower().endswith(".pdf") or not upload_bytes.startswith(b"%PDF"):
            raise BousslaError(ErrorCode.UNSUPPORTED_FILE, "Seuls les PDF sont acceptés")
        limitations: list[str] = []
        try:
            from pypdf import PdfReader
            pages = len(PdfReader(io.BytesIO(upload_bytes)).pages)
        except Exception:  # noqa: BLE001 - any parser failure is an unsupported file
            raise BousslaError(ErrorCode.UNSUPPORTED_FILE, "PDF illisible") from None
        if pages > self.settings.max_pdf_pages:
            raise BousslaError(ErrorCode.LIMIT_EXCEEDED, f"Plus de {self.settings.max_pdf_pages} pages")
        doc_id = f"DOC-{digest[:10].upper()}"
        channel = "COMPANY_UPLOAD" if actor.role is Role.COMPANY else "OFFICER_UPLOAD"
        document = Document(
            document_id=doc_id, subject_company_id=meta["company_id"], case_id=case_id, original_filename=safe_name,
            local_path="", sha256=digest, media_type=media_type, page_count=pages, received_at=utcnow(),
            uploader_actor_id=actor.actor_id, acquisition_channel=channel,
            origin_group_id=f"COMPANY-{meta['company_id']}" if actor.role is Role.COMPANY else "OFFICER-UPLOAD",
            confidentiality_scope="CASE_PARTIES", extraction_status="NOT_RUN", processing_limitations=tuple(limitations))
        # Extraction/routing/integrity (possibly model calls) happen BEFORE the write transaction.
        text = self._text(document, upload_bytes)
        extraction = self._extract(text)
        routing = self._route(document, text)
        integrity = self._inspect(document, upload_bytes)
        if extraction is not None:
            document = document.model_copy(update={"extraction_status": extraction.status})
        _, path = self.store.save_original(upload_bytes, ".pdf")
        document = document.model_copy(update={"local_path": path})
        facts_after = self._prospective_facts(
            case_id, expected_version, document=[document], integrity=[integrity],
            extraction=[extraction] if extraction is not None else [], routing=[routing] if routing is not None else [])
        context_codes = self._auto_context_codes(case_id, meta["company_id"], expected_version, facts_after)
        with self.store.write(case_id) as tx:
            if (prior := tx.find_receipt("upload_document", request_id, ihash)) is not None:
                return DocumentView.model_validate_json(prior)
            tx.require_version(expected_version)
            if any(d.document_id == doc_id for d in self.store.facts(case_id, "document", Document)):
                raise BousslaError(ErrorCode.INVALID_STATE, "Pièce identique déjà déposée dans ce dossier")
            linked_response = self._upload_response_scope(case_id, actor, response_id) if response_id else None
            tx.put("document", doc_id, document)
            if linked_response is not None:
                updated_response = linked_response.model_copy(update={
                    "document_ids": (*linked_response.document_ids, doc_id)})
                tx.put("response", response_id, updated_response)
                facts_after["response"] = [updated_response if r.response_id == response_id else r
                                           for r in facts_after["response"]]
                for proposal in self.store.facts(case_id, "proposal", EvidenceProposal):
                    if proposal.source_response_id == response_id and proposal.source_document_id is None \
                            and proposal.status is ProposalStatus.AWAITING_HUMAN_REVIEW:
                        updated_proposal = proposal.model_copy(update={"source_document_id": doc_id})
                        tx.put("proposal", proposal.proposal_id, updated_proposal)
                        facts_after["proposal"] = [updated_proposal if p.proposal_id == proposal.proposal_id else p
                                                   for p in facts_after["proposal"]]
            if extraction is not None:
                tx.put("extraction", extraction.proposal_id, extraction)
            tx.put("integrity", doc_id, integrity)
            if routing is not None:
                tx.put("routing", doc_id, routing)
            auto = self._auto_clarify(tx, actor, case_id, meta["company_id"], facts_after, context_codes)
            if auto is not None:
                facts_after["request"].append(auto)
            evaluation = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after)
            snapshot = evaluation.score
            from boussla.documents.pipeline import analyze_document
            report = analyze_document(document, extraction, routing, integrity, facts_after,
                                      evaluation.findings, self.clock(), expected_version + 1, text)
            tx.put("document_analysis", doc_id, report)
            v = tx.commit_version(f"Pièce déposée : {safe_name}" + self._auto_reason(auto), score=snapshot)
            tx.event("UPLOAD", actor.actor_id, f"Pièce déposée ({doc_id}) — original conservé, empreinte SHA-256", (doc_id,))
            self._auto_event(tx, auto)
            tx.event("DOCUMENT_ANALYZED", AUTO_ACTOR_ID, "Analyse documentaire terminée ; validation requise", (doc_id,))
            view = DocumentView(document=document, analysis=report if actor.role is Role.OFFICER else None,
                                processing_status="ANALYZED_AWAITING_REVIEW", extraction=extraction, integrity=integrity, routing=routing,
                                case_version=v, mode=Mode.LIVE)
            tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="upload_document", case_id=case_id,
                                          actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                          result_hash=stable_hash(view.model_dump(mode="json"))), view)
        return view

    def _upload_response_scope(self, case_id: str, actor: Actor,
                               response_id: str) -> ClarificationResponse:
        response = self.store.fact(case_id, "response", response_id, ClarificationResponse)
        request = (self.store.fact(case_id, "request", response.request_id, RequestView)
                   if response is not None else None)
        if (response is None or response.author_actor_id != actor.actor_id or actor.role is not Role.COMPANY
                or request is None or request.request.status is not RequestStatus.RESPONDED):
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE,
                               "Réponse inconnue ou hors périmètre pour cette pièce")
        return response

    def _inspect(self, document: Document, content: bytes) -> IntegrityReport:
        fallback = IntegrityReport(document_id=document.document_id, sha256=document.sha256,
                                   limitations=("INTEGRITY_ADAPTER_NOT_RUN",))
        if self.integrity_inspector is None:
            return fallback
        try:
            return self.integrity_inspector.inspect(document, content)
        except Exception:  # noqa: BLE001 - inspection failure is a limitation, never a finding
            return fallback

    def _text(self, document: Document, content: bytes) -> DocumentText | None:
        if self.text_extractor is None:
            return None
        try:
            return self.text_extractor.extract_text(document, content)
        except Exception:  # noqa: BLE001 - unreadable text leaves the manual path
            return None

    def _extract(self, text: DocumentText | None) -> ExtractionProposal | None:
        if text is None:
            return None
        from boussla.documents.allocation import KnownLayoutAllocationExtractor
        allocation = KnownLayoutAllocationExtractor().extract_fields(text)
        if allocation is not None:
            return allocation
        if self.field_extractor is None:
            return None
        try:
            result = self.field_extractor.extract_fields(text)
            if not any(c.normalized_value is not None for c in result.candidates):
                from boussla.documents.labelled import extract_labelled
                result = extract_labelled(text) or result
            from boussla.documents.spans import validate_extraction_proposal
            return validate_extraction_proposal(text, result)
        except BousslaError:
            raise
        except Exception:  # noqa: BLE001 - provider failure is never a finding; manual entry remains
            return None

    def _route(self, document: Document, text: DocumentText | None) -> RouterResult | None:
        """Candidate document class only (Jev or MANUAL fallback). Stored as its own fact;
        never passed to checks, scores or acceptance."""
        if self.document_router is None:
            return None
        manual = RouterResult(document_id=document.document_id, candidate_class=DocumentClass.OTHER_OR_UNKNOWN,
                              mode=Mode.MANUAL)
        body = "\n".join(p.text for p in text.pages) if text is not None and text.status in ("OK", "PARTIAL") else ""
        if not body.strip():
            return manual
        try:
            result = self.document_router.classify(document.document_id, body,
                                                   tuple(c.value for c in DocumentClass))
        except Exception:  # noqa: BLE001 - router outage -> explicit MANUAL
            return manual
        if not isinstance(result, RouterResult) or result.document_id != document.document_id:
            return manual
        return result

    def confirm_transcription(self, actor: Actor, case_id: str, proposal_id: str, field_confirmations: dict[str, str],
                              expected_version: int, request_id: str) -> CompanyCaseView:
        actor, meta = self._open(actor, case_id, "confirm_transcription")
        from boussla.documents.confirmation import confirm_fields
        ihash = self._input_hash(actor, "confirm_transcription", [proposal_id, field_confirmations, expected_version])
        with self.store.write(case_id) as tx:
            if tx.find_receipt("confirm_transcription", request_id, ihash) is None:
                tx.require_version(expected_version)
                proposal = self.store.fact(case_id, "extraction", proposal_id, ExtractionProposal)
                if proposal is None:
                    raise BousslaError(ErrorCode.NOT_FOUND, "Proposition d'extraction inconnue")
                known = {c.field_name for c in proposal.candidates} | set(proposal.missing_fields)
                if not set(field_confirmations) <= known:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Champ non proposé",
                                       fields=sorted(set(field_confirmations) - known))
                document = self.store.fact(case_id, "document", proposal.document_id, Document)
                if document is None or document.subject_company_id != meta["company_id"]:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Document hors périmètre")
                # Native parsing is bounded and local; no model call in this transaction.
                from boussla.documents.native_text import NativePdfExtractor
                text = None
                if document.local_path:
                    with Path(document.local_path).open("rb") as source:
                        content = source.read(self.settings.max_upload_bytes + 1)
                    text = NativePdfExtractor(max_bytes=self.settings.max_upload_bytes,
                                              max_pages=self.settings.max_pdf_pages).extract_text(document, content)
                confirmed = confirm_fields(proposal, field_confirmations, text)
                prior_values = {c.field_name: c.normalized_value for c in proposal.candidates}
                changes = {c.field_name: {"before": prior_values.get(c.field_name), "after": c.normalized_value}
                           for c in confirmed.candidates if c.normalized_value != prior_values.get(c.field_name)}
                tx.put("extraction", proposal_id, confirmed)
                tx.put("transcription_confirmation", proposal_id,
                       {"proposal_id": proposal_id, "fields": {str(k): str(v) for k, v in field_confirmations.items()},
                        "author_actor_id": actor.actor_id, "changes": changes,
                        "calculated_at": self.clock().isoformat(), "rule_version": "transcription-confirmation-2",
                        "note": "Confirmation de transcription, pas d'authenticité"})
                facts_after = self._prospective_facts(case_id, expected_version, extraction=[confirmed])
                evaluation = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after)
                snapshot = evaluation.score
                from boussla.documents.pipeline import analyze_document
                report = analyze_document(document, confirmed,
                    next((r for r in facts_after["routing"] if r.document_id == document.document_id), None),
                    next((r for r in facts_after["integrity"] if r.document_id == document.document_id), None),
                    facts_after, evaluation.findings, self.clock(), expected_version + 1, text)
                tx.put("document_analysis", document.document_id, report)
                v = tx.commit_version("Transcription confirmée par l'entreprise", score=snapshot)
                tx.event("TRANSCRIPTION_CONFIRMED", actor.actor_id, "Transcription confirmée (confirmation ≠ authenticité)",
                         (proposal_id,))
                if changes:
                    tx.event("TRANSCRIPTION_CORRECTED", actor.actor_id,
                             "Champs corrigés : " + ", ".join(sorted(changes)), (proposal_id,))
                tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="confirm_transcription", case_id=case_id,
                                              actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                              result_hash=ihash), ReceiptNote(note="CONFIRMED", fact_ids=(proposal_id,)))
        return self.get_case(actor, case_id)

    def submit_context(self, actor: Actor, case_id: str, context_payload: dict, expected_version: int,
                       request_id: str) -> CompanyCaseView:
        actor, meta = self._open(actor, case_id, "submit_context")
        _reject_unexpected(context_payload, CONTEXT_FIELDS, "Contexte")
        if any(isinstance(v, (dict, list, tuple, set, bool, float)) for v in context_payload.values()):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Contexte : valeurs texte attendues")
        payload = {k: (str(v) if v is not None else None) for k, v in context_payload.items()}
        ihash = self._input_hash(actor, "submit_context", [payload, expected_version])
        try:
            category = PurposeCategory(payload.get("purpose_category") or "OTHER_OR_UNKNOWN")
        except ValueError:
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Catégorie d'usage inconnue") from None
        stock = payload.get("reported_stock_qty") or None
        claim = _validated(
            ContextClaim, claim_id=f"CLAIM-{ihash[:8].upper()}", company_id=meta["company_id"],
            transaction_id=payload.get("transaction_id"), project_id=payload.get("project_id"),
            purpose_category=category, purpose_text=(payload.get("purpose_text") or "")[:2000],
            beneficiary_type=payload.get("beneficiary_type") or "UNKNOWN",
            planned_start=payload.get("planned_start"), planned_end=payload.get("planned_end"),
            stage=payload.get("stage"), reported_stock_qty=_quantity(stock) if stock is not None else None,
            author_actor_id=actor.actor_id, submitted_at=utcnow(),
            supersedes_claim_id=payload.get("supersedes_claim_id"),
            **({"declared_horizon": payload["declared_horizon"]} if payload.get("declared_horizon") else {}))
        facts_after = self._prospective_facts(case_id, expected_version, context_claim=[claim])
        context_codes = self._auto_context_codes(case_id, meta["company_id"], expected_version, facts_after)
        with self.store.write(case_id) as tx:
            if tx.find_receipt("submit_context", request_id, ihash) is None:
                tx.require_version(expected_version)
                projects = {p.project_id for p in self.store.facts(case_id, "project", Project)}
                txs = {t.transaction_id for t in self.store.facts(case_id, "transaction", Transaction)}
                if payload.get("project_id") and payload["project_id"] not in projects:
                    raise BousslaError(ErrorCode.CROSS_COMPANY, "Projet hors du périmètre de l'entreprise")
                if payload.get("transaction_id") and payload["transaction_id"] not in txs:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Transaction inconnue")
                tx.put("context_claim", claim.claim_id, claim)
                auto = self._auto_clarify(tx, actor, case_id, meta["company_id"], facts_after, context_codes)
                if auto is not None:
                    facts_after["request"].append(auto)
                snapshot = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after).score
                v = tx.commit_version("Contexte déclaré par l'entreprise (affirmation attribuée)"
                                      + self._auto_reason(auto), score=snapshot)
                tx.event("CONTEXT", actor.actor_id, "Déclaration de contexte enregistrée (non vérifiée)", (claim.claim_id,))
                self._auto_event(tx, auto)
                tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="submit_context", case_id=case_id,
                                              actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                              result_hash=stable_hash(claim.model_dump(mode="json"))), claim)
        return self.get_case(actor, case_id)

    def start_analysis(self, actor: Actor, case_id: str, expected_version: int, planner=None) -> AnalysisView:
        """Deterministic analysis + question planning. ``planner`` (workflow) may pick
        allowlisted question IDs; its output is validated against the playbook."""
        actor, meta = self._open(actor, case_id, "start_analysis")
        if expected_version != meta["version"]:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le")
        facts = self._facts(case_id, meta["version"])
        ev = self._evaluate(case_id, meta["company_id"], meta["version"], facts)
        officer = actor.role is Role.OFFICER
        modes = {"checks": Mode.LIVE, "retrieval": self._retrieval_mode(), "router": self._router_mode(facts),
                 "extractor": Mode.LIVE if facts["extraction"] else Mode.NOT_RUN}
        answered = self._answered_question_ids(facts)
        rounds = sum(1 for e in self.store.events(case_id) if e.kind == "ANSWERS")  # one per answer batch
        planner_ids, modes["planner"] = self._plan(ev, facts, answered, planner)
        _, context_codes, modes["context"] = self._context_assessment(case_id, meta["company_id"], meta["version"], facts)
        question_ids = merge_question_plan(context_codes, planner_ids, answered)
        status = AnalysisStatus.COMPLETED
        if not officer:
            if rounds >= self.settings.max_question_rounds or not question_ids:
                status, question_ids = AnalysisStatus.NEEDS_OFFICER_REVIEW, []
            else:
                status = AnalysisStatus.AWAITING_COMPANY_ANSWER
        with self.store.write(case_id) as tx:
            tx.event("ANALYSIS_OFFICER" if officer else "ANALYSIS_COMPANY", actor.actor_id,
                     f"Analyse exécutée (checks={ev.score.rules_version}, planner={modes['planner'].value})")
        return AnalysisView(
            analysis_id=f"AN-{case_id}-v{meta['version']}-{actor.role.value[:3]}", case_id=case_id,
            case_version=meta["version"], audience=Audience.OFFICER if officer else Audience.COMPANY, status=status,
            questions=() if officer else scoped_questions(question_ids, ev.findings), question_round=rounds,
            findings=ev.findings if officer else (), hypotheses=ev.hypotheses if officer else (),
            scenarios=ev.scenarios if officer else (), score=ev.score if officer else None,
            mode_by_node=modes, mode=Mode.LIVE)

    @staticmethod
    def _answered_question_ids(facts: dict[str, list]) -> set[str]:
        return {c.purpose_text[1:c.purpose_text.index("]")] for c in facts["context_claim"]
                if c.purpose_text.startswith("[Q-") and "]" in c.purpose_text}

    def _plan(self, ev: Evaluation, facts, answered: set[str], planner) -> tuple[list[str], Mode]:
        has_claim = any(not c.purpose_text.startswith("[Q-") for c in facts["context_claim"])
        fallback = deterministic_plan(ev.findings, has_claim, answered)
        if planner is None:
            return fallback, Mode.TEMPLATE
        try:
            chosen, mode = planner(ev, facts, sorted(set(QUESTIONS) - answered))
        except Exception:  # noqa: BLE001 - model failure -> labelled deterministic fallback
            return fallback, Mode.TEMPLATE
        valid = [q for q in dict.fromkeys(chosen) if q in QUESTIONS and q not in answered][:MAX_QUESTIONS_PER_ROUND]
        return (valid, mode) if valid or not fallback else (fallback, Mode.TEMPLATE)

    def answer_questions(self, actor: Actor, case_id: str, analysis_id: str, answers: dict[str, str],
                         expected_version: int, request_id: str) -> AnalysisView:
        actor, meta = self._open(actor, case_id, "answer_questions")
        if len(answers) > MAX_QUESTIONS_PER_ROUND or any(
                not isinstance(k, str) or not isinstance(v, str) or len(v) > 2000 for k, v in answers.items()):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Réponses hors du schéma ou du budget de questions")
        unknown = set(answers) - set(QUESTIONS)
        if unknown:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Question inconnue", question_ids=sorted(unknown))
        ihash = self._input_hash(actor, "answer_questions", [analysis_id, answers, expected_version])
        with self.store.write(case_id) as tx:
            if tx.find_receipt("answer_questions", request_id, ihash) is None:
                tx.require_version(expected_version)
                ids = []
                new_claims = []
                for qid, text in sorted(answers.items()):
                    claim = ContextClaim(
                        claim_id=f"CLAIM-{stable_hash([ihash, qid])[:8].upper()}", company_id=meta["company_id"],
                        purpose_category=PurposeCategory(text) if qid == "Q-PURPOSE" and text in PurposeCategory.__members__
                        else PurposeCategory.OTHER_OR_UNKNOWN,
                        purpose_text=f"[{qid}] {text}", beneficiary_type="UNKNOWN", author_actor_id=actor.actor_id,
                        submitted_at=utcnow())
                    tx.put("context_claim", claim.claim_id, claim)
                    ids.append(claim.claim_id)
                    new_claims.append(claim)
                superseding = self._superseding_context_claim(actor, meta["company_id"], case_id, answers, ihash)
                from boussla.questionnaire import validate_answers
                validate_answers([QUESTIONS[q] for q in answers], answers)
                if superseding is not None:
                    tx.put("context_claim", superseding.claim_id, superseding)
                    ids.append(superseding.claim_id)
                    new_claims.append(superseding)
                facts_after = self._facts(case_id, expected_version)
                facts_after["context_claim"] = [*self._facts(case_id, expected_version)["context_claim"],
                                               *new_claims]
                snapshot = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after).score
                v = tx.commit_version("Réponses de l'entreprise (affirmations attribuées)", score=snapshot)
                tx.event("ANSWERS", actor.actor_id, "Réponses enregistrées comme affirmations de l'entreprise", tuple(ids))
                tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="answer_questions", case_id=case_id,
                                              actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                              result_hash=ihash), ReceiptNote(note="ANSWERED", fact_ids=tuple(ids)))
        return self.start_analysis(actor, case_id, self.store.case_meta(case_id)["version"])

    def _superseding_context_claim(self, actor: Actor, company_id: str, case_id: str,
                                   answers: dict[str, str], ihash: str):
        """Company answers to structured context questions become a NEW declaration that
        supersedes the latest one (prior claims stay immutable). Never model-written."""
        updates: dict = {}
        if "Q-HORIZON-CONFIRM" in answers:
            value = answers["Q-HORIZON-CONFIRM"].strip().upper()
            if value not in {"SHORT_HORIZON", "LONGER_HORIZON"}:
                raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION,
                                   "Réponse attendue : SHORT_HORIZON ou LONGER_HORIZON", fields=["Q-HORIZON-CONFIRM"])
            updates["declared_horizon"] = value
        if answers.get("Q-PROJECT-STAGE", "").strip():
            updates["stage"] = answers["Q-PROJECT-STAGE"].strip()[:200]
        if answers.get("Q-PROJECT-BENEFICIARY", "").strip():
            updates["beneficiary_type"] = answers["Q-PROJECT-BENEFICIARY"].strip()[:200]
        if answers.get("Q-PURPOSE", "").strip() in PurposeCategory.__members__:
            updates["purpose_category"] = answers["Q-PURPOSE"].strip()
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", answers.get("Q-PROJECT-DATES", ""))
        if len(dates) == 2:
            updates["planned_start"], updates["planned_end"] = dates
        base = self._context_base_claim(company_id, {"context_claim": self.store.facts(case_id, "context_claim",
                                                                                      ContextClaim)})
        if not updates or base is None:
            return None
        data = {**base.model_dump(), **updates, "claim_id": f"CLAIM-{stable_hash([ihash, 'context'])[:8].upper()}",
                "supersedes_claim_id": base.claim_id, "author_actor_id": actor.actor_id, "submitted_at": utcnow()}
        return _validated(ContextClaim, **data)

    # ------------------------------------------------------- automatic clarification
    # company submission -> deterministic evaluation -> context consistency -> question plan
    # -> (if needed) ONE neutral fixed-catalogue request, published in the SAME transaction
    # (and revision) as the submission. Retries replay the submission's receipt, so a request
    # is never duplicated. Human review stays mandatory for evidence, canonical changes and
    # any decision: this step only asks allowlisted questions.
    def _auto_context_codes(self, case_id: str, company_id: str, expected_version: int,
                            facts_after: dict[str, list] | None) -> tuple[str, ...]:
        """Pre-transaction (may call the context interpreter, cached per version)."""
        if facts_after is None:
            return ()
        return self._context_assessment(case_id, company_id, expected_version + 1, facts_after)[1]

    def _prospective_facts(self, case_id: str, expected_version: int, replace: dict | None = None,
                           **additions) -> dict[str, list] | None:
        """Facts of version ``expected_version`` plus this write's uncommitted facts, or None
        when the case already moved on (the write will then be refused or replayed)."""
        if self.store.case_meta(case_id)["version"] != expected_version:
            return None
        facts = self._facts(case_id, expected_version)
        facts.update(replace or {})
        for kind, items in additions.items():
            facts[kind] = [*facts[kind], *items]
        return facts

    def _automatic_question_ids(self, ev: Evaluation, facts: dict[str, list], context_codes,
                                case_id: str | None = None) -> list[str]:
        requests = facts["request"]
        if any(r.request.status in PENDING_STATUSES for r in requests):
            return []  # one open request at a time
        if any(p.status is ProposalStatus.AWAITING_HUMAN_REVIEW for p in facts["proposal"]):
            return []  # the next step belongs to the officer
        published = [r for r in requests if r.request.status is not RequestStatus.DRAFT]
        if len(published) >= self.settings.max_question_rounds:
            return []  # configured round budget exhausted
        asked = self._answered_question_ids(facts) | fully_asked_questions(ev.findings, published)
        has_claim = any(not c.purpose_text.startswith("[Q-") for c in facts["context_claim"])
        return merge_question_plan(context_codes, self._planner_ids(ev, has_claim, asked, case_id), asked)

    def _planner_ids(self, ev: Evaluation, has_claim: bool, asked: set[str], case_id: str | None) -> list[str]:
        """Deterministic finding plan first; the latest investigator suggestions (allowlisted
        IDs only) can fill remaining slots. The global merge still caps a round at 3."""
        planned = deterministic_plan(ev.findings, has_claim, asked)
        suggested = [q for q in self._brief_questions.get(case_id or "", ()) if q in QUESTIONS and q not in asked]
        return list(dict.fromkeys(planned + suggested))

    def _auto_clarify(self, tx, actor: Actor, case_id: str, company_id: str, facts_after: dict[str, list] | None,
                      context_codes) -> RequestView | None:
        """Inside the submission's write transaction, before ``commit_version``."""
        if actor.role is not Role.COMPANY or facts_after is None:
            return None
        version = tx.begin_version()
        with traced("auto_clarification", case_id, case_version=version) as meta:
            ev = self._evaluate(case_id, company_id, version, facts_after)
            qids = self._automatic_question_ids(ev, facts_after, context_codes, case_id)
            meta.update(mode="PUBLISHED" if qids else "SKIPPED", question_count=len(qids),
                        finding_count=sum(f.status is FindingStatus.UNRESOLVED for f in ev.findings))
        questions = scoped_questions(qids, ev.findings, facts_after["request"])
        qids = [q.question_id for q in questions]
        if not qids:
            return None
        reasons = tuple(dict.fromkeys([str(getattr(c, "value", c)) for c in context_codes] + [
            f.reason_code for f in ev.findings if f.status in (FindingStatus.UNRESOLVED, FindingStatus.INSUFFICIENT)
            and f.reason_code]))[:10]
        now = self.clock()
        fact_ids = tuple(dict.fromkeys(
            r.source_record_id or r.document_id for f in ev.findings if f.status is FindingStatus.UNRESOLVED
            for r in f.evidence_refs if (r.source_record_id or r.document_id)))
        req = ClarificationRequest(
            request_id=f"REQ-AUTO-{stable_hash([case_id, version, qids])[:8].upper()}", case_id=case_id,
            company_id=company_id, case_version=version, fact_ids=fact_ids, question_ids=tuple(qids),
            allowed_document_types=ALLOWED_RESPONSE_DOCUMENTS, target_response_at=now + timedelta(days=FOLLOW_UP_DAYS),
            status=RequestStatus.PUBLISHED_IN_DEMO, approved_by=None, published_at=now, available_in_inbox_at=now,
            origin="AUTOMATIC", reason_codes=reasons, reason_text_fr=AUTO_REASON_TEXT_FR)
        view = RequestView(request=req, questions=questions, text_fr=AUTO_REQUEST_TEXT_FR,
                           mode=Mode.TEMPLATE)
        tx.put("request", req.request_id, view)
        return view

    @staticmethod
    def _auto_reason(auto: RequestView | None) -> str:
        return " ; demande de précision automatique publiée (catalogue fixe)" if auto else ""

    @staticmethod
    def _auto_event(tx, auto: RequestView | None) -> None:
        if auto is not None:
            tx.event("AUTO_CLARIFICATION_PUBLISHED", AUTO_ACTOR_ID,
                     f"Demande de précision automatique publiée ({len(auto.questions)} question(s) du catalogue fixe, "
                     "aucune décision, aucun envoi externe)", (auto.request.request_id,))

    # ------------------------------------------------------- clarification
    def prepare_clarification(self, actor: Actor, case_id: str, expected_version: int) -> ClarificationDraft:
        actor, meta = self._open(actor, case_id, "prepare_clarification")
        if expected_version != meta["version"]:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le")
        facts = self._facts(case_id, meta["version"])
        ev = self._evaluate(case_id, meta["company_id"], meta["version"], facts)
        # Same global merge policy as start_analysis: context contradictions first, one cap of 3.
        _, context_codes, _ = self._context_assessment(case_id, meta["company_id"], meta["version"], facts)
        # An officer may deliberately request a follow-up after a response/rejection.
        # Duplicate open publications are reused or refused below; automatic reminders stay deduplicated.
        qids = merge_question_plan(context_codes, self._planner_ids(ev, True, set(), case_id), set())
        questions = scoped_questions(qids, ev.findings)
        if not questions:
            raise BousslaError(ErrorCode.INVALID_STATE, "Aucune nouvelle question pertinente à publier")
        fact_ids = tuple(dict.fromkeys(
            r.source_record_id or r.document_id for f in ev.findings if f.status is FindingStatus.UNRESOLVED
            for r in f.evidence_refs if (r.source_record_id or r.document_id)))
        draft = ClarificationDraft(
            draft_id=f"DRAFT-{uuid.uuid4().hex[:8].upper()}", case_id=case_id, company_id=meta["company_id"],
            case_version=meta["version"], questions=questions, fact_ids=fact_ids,
            allowed_document_types=ALLOWED_RESPONSE_DOCUMENTS,
            target_response_at=utcnow() + timedelta(days=FOLLOW_UP_DAYS), text_fr=REQUEST_TEXT_FR, mode=Mode.TEMPLATE)
        self.store.put_artifact(case_id, "draft", draft.draft_id, meta["version"], draft)
        return draft

    def publish_clarification(self, actor: Actor, case_id: str, draft_id: str, expected_version: int,
                              request_id: str) -> RequestView:
        actor, meta = self._open(actor, case_id, "publish_clarification")
        ihash = self._input_hash(actor, "publish_clarification", [draft_id, expected_version])
        stored = self.store.artifact(case_id, "draft", draft_id, ClarificationDraft)
        with self.store.write(case_id) as tx:
            if (prior := tx.find_receipt("publish_clarification", request_id, ihash)) is not None:
                return RequestView.model_validate_json(prior)
            tx.require_version(expected_version)
            if stored is None:
                raise BousslaError(ErrorCode.NOT_FOUND, "Brouillon inconnu")
            draft_version, draft = stored
            if draft_version != expected_version:
                raise BousslaError(ErrorCode.STALE_REVISION, "Brouillon lié à une ancienne version ; préparez-en un nouveau")
            existing = self.store.facts(case_id, "request", RequestView)
            pending = next((r for r in existing if r.request.status in PENDING_STATUSES), None)
            if pending is not None:
                if pending.questions == draft.questions:
                    tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="publish_clarification",
                        case_id=case_id, actor_id=actor.actor_id, input_hash=ihash,
                        resulting_version=expected_version, result_hash=stable_hash(pending.model_dump(mode="json"))), pending)
                    return pending
                raise BousslaError(ErrorCode.INVALID_STATE, "Une demande est déjà en attente de réponse")
            if not 0 < len(draft.questions) <= MAX_QUESTIONS_PER_ROUND:
                raise BousslaError(ErrorCode.INVALID_INPUT, "Nombre de questions invalide")
            now = utcnow()
            req = ClarificationRequest(
                request_id=f"REQ-{draft_id[6:]}", case_id=case_id, company_id=meta["company_id"],
                case_version=expected_version, fact_ids=draft.fact_ids,
                question_ids=tuple(q.question_id for q in draft.questions),
                allowed_document_types=draft.allowed_document_types, target_response_at=draft.target_response_at,
                status=RequestStatus.PUBLISHED_IN_DEMO, approved_by=actor.actor_id, published_at=now,
                available_in_inbox_at=now)
            view = RequestView(request=req, questions=draft.questions, text_fr=draft.text_fr, mode=Mode.TEMPLATE)
            tx.put("request", req.request_id, view)
            facts_after = self._facts(case_id, expected_version)
            facts_after["request"].append(view)
            snapshot = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after).score
            v = tx.commit_version("Demande de précision publiée dans la boîte de démonstration", score=snapshot)
            tx.event("REQUEST_PUBLISHED", actor.actor_id, "Demande publiée localement (aucun e-mail/SMS/portail)",
                     (req.request_id,))
            tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="publish_clarification", case_id=case_id,
                                          actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                          result_hash=stable_hash(view.model_dump(mode="json"))), view)
        return view

    def submit_response(self, actor: Actor, case_id: str, request_id: str, payload: dict, expected_version: int,
                        idempotency_key: str) -> ResponseView:
        """payload: {"answers": {question_id: text}, "document_ids": [...],
        "allocation": {"transaction_id", "line_id", "splits": {project_id: quantity}}}.
        ``allocation`` becomes an EvidenceProposal awaiting officer review — never a change by itself."""
        actor, meta = self._open(actor, case_id, "submit_response")
        _reject_unexpected(payload, RESPONSE_FIELDS, "Réponse")
        raw_answers, raw_docs = payload.get("answers") or {}, payload.get("document_ids") or ()
        if not isinstance(raw_answers, dict) or not isinstance(raw_docs, (list, tuple)):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Réponse : answers (objet) et document_ids (liste) attendus")
        if any(not isinstance(k, str) or not isinstance(v, str) or len(v) > 2000 for k, v in raw_answers.items()):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Les réponses doivent être des textes de 2000 caractères maximum")
        answers = dict(raw_answers)
        doc_ids = tuple(str(d) for d in raw_docs)
        alloc = self._allocation_input(payload.get("allocation"))
        ihash = self._input_hash(actor, "submit_response", [request_id, answers, doc_ids, alloc, expected_version])
        # Built before the transaction (the context interpreter may run for the automatic step).
        superseding = self._superseding_context_claim(actor, meta["company_id"], case_id, answers, ihash)
        response = ClarificationResponse(
            response_id=f"RESP-{ihash[:8].upper()}", request_id=request_id, author_actor_id=actor.actor_id,
            document_ids=doc_ids, answers=answers, submitted_at=utcnow())
        facts_after = None  # an allocation always leaves a proposal for the officer: no automatic request
        if alloc is None:
            facts_after = self._prospective_facts(case_id, expected_version, response=[response],
                                                  context_claim=[superseding] if superseding else [])
            if facts_after is not None:
                facts_after["request"] = [r.model_copy(update={"request": r.request.model_copy(update={
                    "status": RequestStatus.RESPONDED})}) if r.request.request_id == request_id else r
                    for r in facts_after["request"]]
        context_codes = self._auto_context_codes(case_id, meta["company_id"], expected_version, facts_after)
        with self.store.write(case_id) as tx:
            if (prior := tx.find_receipt("submit_response", idempotency_key, ihash)) is not None:
                return ResponseView.model_validate_json(prior)
            tx.require_version(expected_version)
            rv = self.store.fact(case_id, "request", request_id, RequestView)
            if rv is None or rv.request.status is not RequestStatus.PUBLISHED_IN_DEMO:
                raise BousslaError(ErrorCode.INVALID_STATE, "Aucune demande publiée correspondante")
            if not set(answers) <= set(rv.request.question_ids):
                raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Réponse à une question non posée")
            from boussla.questionnaire import validate_answers
            validate_answers(rv.questions, answers)
            docs = {d.document_id: d for d in self.store.facts(case_id, "document", Document)}
            for d in doc_ids:
                if d not in docs or docs[d].subject_company_id != meta["company_id"]:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Pièce inconnue ou hors périmètre")
            tx.put("response", response.response_id, response)
            # Structured context answers (e.g. Q-HORIZON-CONFIRM) become a new attributed claim
            # superseding the latest declaration, exactly as in answer_questions.
            if superseding is not None:
                tx.put("context_claim", superseding.claim_id, superseding)
            tx.put("request", request_id, rv.model_copy(update={
                "request": rv.request.model_copy(update={"status": RequestStatus.RESPONDED})}))
            proposal_ids: tuple[str, ...] = ()
            if alloc is not None:
                proposal = self._build_proposal(case_id, meta["company_id"], expected_version + 1, alloc,
                                                response.response_id, doc_ids[0] if doc_ids else None)
                tx.put("proposal", proposal.proposal_id, proposal)
                proposal_ids = (proposal.proposal_id,)
            auto = self._auto_clarify(tx, actor, case_id, meta["company_id"], facts_after, context_codes)
            if facts_after is None:
                facts_after = self._prospective_facts(case_id, expected_version)
            if facts_after is not None:
                if all(r.response_id != response.response_id for r in facts_after["response"]):
                    facts_after["response"].append(response)
                if superseding is not None and all(c.claim_id != superseding.claim_id for c in facts_after["context_claim"]):
                    facts_after["context_claim"].append(superseding)
                facts_after["request"] = [rv.model_copy(update={"request": rv.request.model_copy(update={
                    "status": RequestStatus.RESPONDED})}) if r.request.request_id == request_id else r
                    for r in facts_after["request"]]
                if alloc is not None:
                    facts_after["proposal"].append(proposal)
                if auto is not None:
                    facts_after["request"].append(auto)
                snapshot = self._evaluate(case_id, meta["company_id"], expected_version + 1, facts_after).score
            else:
                snapshot = None
            v = tx.commit_version("Réponse de l'entreprise reçue (proposition, pas une acceptation)"
                                  + self._auto_reason(auto), score=snapshot)
            tx.event("RESPONSE", actor.actor_id, "Réponse reçue ; en attente de revue par l'agent",
                     (response.response_id, *proposal_ids))
            self._auto_event(tx, auto)
            view = ResponseView(response=response, proposal_ids=proposal_ids, case_version=v, mode=Mode.LIVE)
            tx.save_receipt(ActionReceipt(idempotency_key=idempotency_key, action="submit_response", case_id=case_id,
                                          actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                          result_hash=stable_hash(view.model_dump(mode="json"))), view)
        return view

    @staticmethod
    def _allocation_input(alloc: object) -> dict | None:
        """Strict allocation payload -> canonical dict (None when absent). A quantity
        allocation carries no currency; a stated unit must match the invoice line (checked
        in ``_build_proposal``); unknown properties are refused, never silently dropped."""
        if alloc is None or alloc == {}:
            return None
        if not isinstance(alloc, dict):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Affectation : objet attendu")
        if "currency" in alloc:
            raise BousslaError(ErrorCode.INCOMPATIBLE_UNIT, "Une affectation porte sur des quantités : "
                               "aucune devise ne peut y être indiquée", fields=["currency"])
        _reject_unexpected(alloc, ALLOCATION_FIELDS, "Affectation")
        splits = alloc.get("splits")
        if not isinstance(splits, dict) or not splits:
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Répartition par lot requise", fields=["splits"])
        if len(splits) > 20 or any(not isinstance(k, str) or not 0 < len(k) <= 64 for k in splits):
            raise BousslaError(ErrorCode.INVALID_INPUT, "Affectation : identifiants de lot invalides", fields=["splits"])
        for name in ("transaction_id", "line_id", "unit"):
            if name in alloc and not isinstance(alloc[name], str):
                raise BousslaError(ErrorCode.INVALID_INPUT, f"Affectation : {name} doit être un texte", fields=[name])
        out = {"transaction_id": alloc.get("transaction_id", ""), "line_id": alloc.get("line_id", ""),
               "splits": {k: _quantity(v) for k, v in sorted(splits.items())}}
        if "unit" in alloc:
            out["unit"] = alloc["unit"].strip()
        return out

    def _build_proposal(self, case_id: str, company_id: str, version: int, alloc: dict, response_id: str,
                        document_id: str | None) -> EvidenceProposal:
        """Shape-check a proposed reallocation (``alloc`` from ``_allocation_input``).
        Full scope/budget checks run again at acceptance."""
        tx_id, line_id, splits = alloc["transaction_id"], alloc["line_id"], alloc["splits"]
        line = next((ln for o in self.store.facts(case_id, "invoice_observation", InvoiceObservation)
                     if o.transaction_id == tx_id and o.perspective is Perspective.BUYER_RECEIVED
                     for ln in o.lines if ln.line_id == line_id), None)
        if line is None:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Transaction ou ligne inconnue")
        if "unit" in alloc and alloc["unit"] != line.unit:
            raise BousslaError(ErrorCode.INCOMPATIBLE_UNIT, "Unité différente de la ligne de facture", fields=["unit"])
        current = {a.target_project_id: a for a in self.store.facts(case_id, "allocation", Allocation)
                   if a.transaction_id == tx_id and a.line_id == line_id and a.status is AllocationStatus.ACCEPTED}
        changes = []
        for project_id, qty in splits.items():
            existing = current.get(project_id)
            changes.append(AllocationChange(
                action="REPLACE" if existing else "CREATE",
                allocation_id=existing.allocation_id if existing else f"ALLOC-{project_id}-{response_id[5:]}",
                target_project_id=project_id, target_type=AllocationTarget.PROJECT,
                old_quantity=existing.quantity if existing else None, new_quantity=qty))
        return EvidenceProposal(
            proposal_id=f"PROP-{response_id[5:]}", case_id=case_id, expected_version=version,
            source_document_id=document_id, source_response_id=response_id, transaction_id=tx_id, line_id=line_id,
            unit=line.unit, budget_quantity=line.quantity, changes=tuple(changes),
            status=ProposalStatus.AWAITING_HUMAN_REVIEW)

    # ------------------------------------------------------- evidence review
    def accept_evidence(self, actor: Actor, case_id: str, proposal_id: str, expected_version: int,
                        idempotency_key: str) -> RevisionResult:
        return self._decide(actor, case_id, proposal_id, expected_version, idempotency_key, accept=True, reason=None)

    def reject_evidence(self, actor: Actor, case_id: str, proposal_id: str, expected_version: int, reason: str,
                        idempotency_key: str) -> RevisionResult:
        return self._decide(actor, case_id, proposal_id, expected_version, idempotency_key, accept=False,
                            reason=str(reason)[:500])

    def _decide(self, actor: Actor, case_id: str, proposal_id: str, expected_version: int, key: str,
                accept: bool, reason: str | None) -> RevisionResult:
        action = "accept_evidence" if accept else "reject_evidence"
        actor, meta = self._open(actor, case_id, action)
        ihash = self._input_hash(actor, action, [proposal_id, reason])
        with self.store.write(case_id) as tx:
            # 1) Identical authorized retry returns the stored outcome BEFORE the version check.
            if (prior := tx.find_receipt(action, key, ihash)) is not None:
                return RevisionResult.model_validate_json(prior).model_copy(update={"replayed": True})
            # 2) New action: version, proposal state and scope, all inside the transaction.
            previous = tx.require_version(expected_version)
            facts = self._facts(case_id, previous)
            proposal = next((p for p in facts["proposal"] if p.proposal_id == proposal_id), None)
            if proposal is None or proposal.case_id != case_id:
                raise BousslaError(ErrorCode.NOT_FOUND, "Proposition inconnue pour ce dossier")
            if proposal.status is not ProposalStatus.AWAITING_HUMAN_REVIEW:
                raise BousslaError(ErrorCode.DUPLICATE_ACCEPTANCE, "Proposition déjà traitée")
            before = self._evaluate(case_id, meta["company_id"], previous, facts)
            new_allocations = facts["allocation"]
            if accept:
                self._require_supporting_document(proposal, facts, meta["company_id"])
                new_allocations = self._apply_proposal(proposal, facts, meta["company_id"])
                for a in new_allocations:
                    old = next((x for x in facts["allocation"] if x.allocation_id == a.allocation_id), None)
                    if old != a:
                        tx.put("allocation", a.allocation_id, a)
            decision = {"status": ProposalStatus.ACCEPTED if accept else ProposalStatus.REJECTED,
                        "decided_by": actor.actor_id, "decided_at": self.clock(), "decision_reason": reason}
            tx.put("proposal", proposal_id, proposal.model_copy(update=decision))
            after_facts = {**facts, "allocation": new_allocations,
                           "proposal": [p if p.proposal_id != proposal_id else p.model_copy(update=decision)
                                        for p in facts["proposal"]]}
            after = self._evaluate(case_id, meta["company_id"], previous + 1, after_facts, before.score)
            v = tx.commit_version(("Pièce acceptée dans ce dossier : " if accept else "Pièce rejetée : ")
                                  + (reason or proposal_id), (proposal_id,) if accept else (), score=after.score)
            tx.event("EVIDENCE_ACCEPTED" if accept else "EVIDENCE_REJECTED", actor.actor_id,
                     "Acceptée dans ce dossier par l'agent (pas une authentification)" if accept
                     else f"Rejetée par l'agent : {reason or '—'}", (proposal_id,), before_score=before.score, after_score=after.score)
            result_body = {"after": [a.model_dump(mode="json") for a in new_allocations], "index": after.score.review_index}
            receipt = ActionReceipt(idempotency_key=key, action=action, case_id=case_id, actor_id=actor.actor_id,
                                    input_hash=ihash, resulting_version=v, result_hash=stable_hash(result_body))
            result = RevisionResult(
                case_id=case_id, outcome="ACCEPTED" if accept else "REJECTED", previous_version=previous,
                new_version=v, receipt=receipt, allocations_before=tuple(facts["allocation"]),
                allocations_after=tuple(new_allocations), findings_before=before.findings,
                findings_after=after.findings, score_before=before.score, score_after=after.score, mode=Mode.LIVE)
            tx.save_receipt(receipt, result)
        return result

    @staticmethod
    def _require_supporting_document(proposal: EvidenceProposal, facts: dict[str, list], company_id: str) -> None:
        """A declaration alone is never evidence: acceptance (the only path that changes
        canonical allocations and therefore the review index) needs a supporting document
        stored in this case, for this company, and attached to the same response."""
        response = next((r for r in facts["response"] if r.response_id == proposal.source_response_id), None)
        document = next((d for d in facts["document"] if d.document_id == proposal.source_document_id), None)
        if (proposal.source_document_id is None or document is None or document.subject_company_id != company_id
                or response is None or proposal.source_document_id not in response.document_ids):
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION,
                               "Déclaration sans pièce justificative : elle peut être rejetée ou complétée, "
                               "pas acceptée comme preuve", reason="SUPPORTING_DOCUMENT_REQUIRED")

    def _apply_proposal(self, proposal: EvidenceProposal, facts: dict[str, list], company_id: str) -> list[Allocation]:
        """Validate scope + budget and return the full post-acceptance allocation ledger."""
        line = next((ln for o in facts["invoice_observation"]
                     if o.transaction_id == proposal.transaction_id and o.perspective is Perspective.BUYER_RECEIVED
                     for ln in o.lines if ln.line_id == proposal.line_id), None)
        if line is None:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Ligne de facture inconnue")
        if proposal.unit != line.unit:
            raise BousslaError(ErrorCode.INCOMPATIBLE_UNIT, "Unité différente de la facture")
        projects = {p.project_id for p in facts["project"] if p.company_id == company_id}
        by_id = {a.allocation_id: a for a in facts["allocation"]}
        template = next((a for a in facts["allocation"]
                         if a.transaction_id == proposal.transaction_id and a.line_id == proposal.line_id), None)
        today = utcnow().date()
        for ch in proposal.changes:
            if ch.target_type is AllocationTarget.PROJECT and ch.target_project_id not in projects:
                raise BousslaError(ErrorCode.CROSS_COMPANY, "Lot hors du périmètre de l'entreprise")
            if ch.action == "REPLACE":
                current = by_id.get(ch.allocation_id)
                if current is None or current.quantity != ch.old_quantity or current.status is not AllocationStatus.ACCEPTED:
                    raise BousslaError(ErrorCode.STALE_REVISION, "L'affectation a changé depuis la proposition")
                by_id[ch.allocation_id] = current.model_copy(update={
                    "quantity": ch.new_quantity, "effective_on": today,
                    "source_refs": tuple(x for x in (proposal.source_document_id, proposal.source_response_id) if x)})
            else:
                if ch.allocation_id in by_id:
                    raise BousslaError(ErrorCode.DUPLICATE_ACCEPTANCE, "Affectation déjà existante")
                by_id[ch.allocation_id] = Allocation(
                    allocation_id=ch.allocation_id, transaction_id=proposal.transaction_id, line_id=proposal.line_id,
                    target_project_id=ch.target_project_id, target_type=ch.target_type, quantity=ch.new_quantity,
                    unit=proposal.unit, effective_on=template.effective_on if template else today,
                    source_refs=tuple(x for x in (proposal.source_document_id, proposal.source_response_id) if x),
                    status=AllocationStatus.ACCEPTED, fact_kind="OFFICER_ACCEPTED_REALLOCATION")
        used = sum((Decimal(a.quantity) for a in by_id.values()
                    if a.transaction_id == proposal.transaction_id and a.line_id == proposal.line_id
                    and a.status is AllocationStatus.ACCEPTED), Decimal(0))
        if used > Decimal(line.quantity):
            raise BousslaError(ErrorCode.ALLOCATION_OVERFLOW, "Quantités affectées supérieures à la quantité facturée",
                               used=str(used), available=line.quantity)
        return sorted(by_id.values(), key=lambda a: a.allocation_id)

    # ----------------------------------------------------------------- export
    def export_dossier(self, actor: Actor, case_id: str, audience: Audience, expected_version: int) -> LocalDraftArtifact:
        actor, meta = self._open(actor, case_id, "export_dossier")
        audience = Audience(audience)
        if expected_version != meta["version"]:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le")
        v = meta["version"]
        facts = self._facts(case_id, v)
        lines = [f"# Dossier {case_id} — version {v}", "",
                 f"Entreprise : {self._company_name(meta['company_id'])}", "",
                 "> Brouillon local de démonstration. Aucune valeur juridique ; aucune notification envoyée.", ""]
        if audience is Audience.OFFICER:
            ev = self._evaluate(case_id, meta["company_id"], v, facts)
            lines += ["## Constats (priorité de revue, pas une probabilité de fraude)", ""]
            lines += [f"- {f.family.value} / {f.transaction_id} : {f.status.value} — {f.reason_code or ''}"
                      + (f" (écart {f.quantity_difference} {f.unit})" if f.quantity_difference else "") for f in ev.findings]
            lines += ["", f"Indice de priorité : {ev.score.review_index} — couverture : {ev.score.evidence_coverage} %", "",
                      "## Hypothèses", ""] + [f"- {h.hypothesis_id} : {h.status.value}" for h in ev.hypotheses]
        else:
            lines += ["## Questions publiées", ""]
            lines += [f"- {q.text_fr}" for r in facts["request"] for q in r.questions]
            lines += ["", "## Affectations enregistrées", ""]
            lines += [f"- {a.target_project_id} : {a.quantity} {a.unit}" for a in facts["allocation"]]
        with self.store.write(case_id) as tx:
            tx.event("EXPORT", actor.actor_id, f"Brouillon local exporté ({audience.value})")
        return LocalDraftArtifact(
            artifact_id=f"ART-{uuid.uuid4().hex[:8].upper()}", case_id=case_id, audience=audience, case_version=v,
            filename=f"{case_id}_v{v}_{audience.value.lower()}.md", content_markdown="\n".join(lines),
            generated_at=utcnow(), mode=Mode.TEMPLATE,
            disclaimer_fr="Brouillon de démonstration ; aucune valeur juridique ; aucune notification envoyée.")


def _discover_investigator():
    """Lane C officer investigator (OpenAI selector when configured, else TEMPLATE)."""
    try:
        from boussla.investigator import investigator_assistant
        return investigator_assistant()
    except Exception:  # noqa: BLE001 - optional assistive layer
        return None


def _discover_document_adapters(settings: Settings) -> dict:
    """Lane C adapters when merged; absent modules leave the manual path (None)."""
    found: dict = {}
    try:
        from boussla.documents.native_text import NativePdfExtractor
        found["text_extractor"] = NativePdfExtractor(max_bytes=settings.max_upload_bytes,
                                                     max_pages=settings.max_pdf_pages)
    except ImportError:
        return found
    try:
        from boussla.documents.integrity import PdfIntegrityInspector
        found["integrity_inspector"] = PdfIntegrityInspector()
    except ImportError:
        pass
    try:
        if settings.llm_provider == "openai" and settings.secret("OPENAI_API_KEY"):
            from boussla.adapters.model_extraction import OpenAIInvoiceExtractor
            found["field_extractor"] = OpenAIInvoiceExtractor(api_key=settings.secret("OPENAI_API_KEY"))
        else:
            from boussla.documents.known_layout import KnownLayoutInvoiceExtractor
            found["field_extractor"] = KnownLayoutInvoiceExtractor()
    except ImportError:
        pass
    if settings.jev_enabled:
        try:
            from boussla.adapters.jev import JevDocumentRouter
            found["document_router"] = JevDocumentRouter(api_key=settings.secret("TYPESAFE_API_KEY"),
                                                         model=settings.jev_model)
        except ImportError:
            pass
    return found


def _discover_context_assistant():
    """Lane C context-consistency assistant, built once per service/process. Without an
    OpenAI key the interpreter is NOT_RUN and date calculation still runs."""
    try:
        from boussla.context.assistant import context_consistency_assistant
        return context_consistency_assistant()
    except Exception:  # noqa: BLE001 - optional auxiliary layer
        return None


def _discover_reference_assistant():
    """Lane C officer reference assistant: Qdrant Cloud when QDRANT_URL/QDRANT_API_KEY are
    set (else labelled lexical), plus the OpenAI note generator when configured. Any
    construction failure disables enrichment (retrieval NOT_RUN) instead of failing startup."""
    try:
        from boussla.retrieval.grounded_rag import public_reference_assistant
        return public_reference_assistant()
    except Exception:  # noqa: BLE001 - optional enrichment; no secret or reason exposed
        return None


def build_service(settings: Settings | None = None, seed: bool = True) -> BousslaAppService:
    """Default wiring: SQLite at CASE_DB_PATH, demo roster, B's checks (or the
    labelled interim engine) and C's document adapters when present."""
    settings = settings or get_settings()
    use_os_trust_store()
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    if seed:
        seed_demo_case(store)
    portfolio = None
    if settings.portfolio_enabled:
        from boussla.portfolio_runtime import PortfolioRuntime
        portfolio = PortfolioRuntime(settings.portfolio_state_path)
    svc = BousslaAppService(store, settings=settings, reference_assistant=_discover_reference_assistant(),
                            context_assistant=_discover_context_assistant(), investigator=_discover_investigator(),
                            portfolio=portfolio, **_discover_document_adapters(settings))
    if portfolio is not None and seed:
        _materialize(svc)
    elif portfolio is not None:  # existing cases only: assign them, create nothing
        for e in portfolio.enterprises():
            if store.case_exists(portfolio.case_id(e.company_id)):
                for officer in _officers(svc):
                    svc.registry.assign(officer, portfolio.case_id(e.company_id))
    return svc
