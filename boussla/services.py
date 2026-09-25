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
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from boussla.config import Settings, get_settings
from boussla.contracts import (
    Actor, Allocation, AllocationChange, AllocationStatus, AllocationTarget, AnalysisStatus, AnalysisView,
    Audience, BousslaError, ClarificationDraft, ClarificationRequest, ClarificationResponse, ClarificationStatus,
    CompanyCaseView, ContextClaim, Delivery, Document, DocumentView, ErrorCode, EvidenceProposal, Finding,
    FindingFamily, FindingStatus, HistoryView, Hypothesis, IdentityMapping, IntegrityReport, InvoiceObservation,
    LocalDraftArtifact, Mode, OfficerCaseView, Payment, PaymentAllocation, PaymentStatus, Perspective, Project,
    ProposalStatus, PurposeCategory, QuantityReference, QueueItem, QueuePage, RequestStatus, RequestView,
    ResponseView, RevisionResult, Role, Scenario, ScoreSnapshot, Transaction, TransactionInputs,
    TransactionSummary, ActionReceipt, ExtractionProposal,
)
from boussla.interim_checks import get_checks_engine
from boussla.playbook import (
    ALLOWED_RESPONSE_DOCUMENTS, MAX_QUESTIONS_PER_ROUND, QUESTIONS, REQUEST_TEXT_FR, deterministic_plan,
)
from boussla.security import DEMO_BANNER_FR, ActorRegistry, authorize
from boussla.seed import load_enterprises, seed_demo_case
from boussla.store import CaseStore, ReceiptNote, stable_hash, utcnow

ALL_FAMILIES = frozenset(FindingFamily)
FOLLOW_UP_DAYS = 7


@dataclass(frozen=True)
class Evaluation:
    """Deterministic analysis of one case version (derived, never stored as fact)."""

    version: int
    findings: tuple[Finding, ...]
    hypotheses: tuple[Hypothesis, ...]
    scenarios: tuple[Scenario, ...]
    score: ScoreSnapshot


class BousslaAppService:
    mode = Mode.LIVE

    def __init__(self, store: CaseStore, registry: ActorRegistry | None = None, checks=None,
                 settings: Settings | None = None, field_extractor=None, text_extractor=None) -> None:
        self.store = store
        self.registry = registry or ActorRegistry.demo()
        self.checks = checks or get_checks_engine()
        self.settings = settings or get_settings()
        self.enterprises = load_enterprises()
        self.text_extractor = text_extractor
        self.field_extractor = field_extractor

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
            "document": s.facts(case_id, "document", Document, v),
            "project": s.facts(case_id, "project", Project, v),
            "request": s.facts(case_id, "request", RequestView, v),
            "response": s.facts(case_id, "response", ClarificationResponse, v),
            "proposal": s.facts(case_id, "proposal", EvidenceProposal, v),
            "extraction": s.facts(case_id, "extraction", ExtractionProposal, v),
        }

    def _clarification_status(self, requests: list[RequestView]) -> ClarificationStatus:
        """Administrative status only; never an input to the review index."""
        statuses = [r.request.status for r in requests]
        if not statuses:
            return ClarificationStatus.NOT_REQUESTED
        if RequestStatus.PUBLISHED_IN_DEMO in statuses:
            return ClarificationStatus.PENDING
        if RequestStatus.EXTENDED in statuses:
            return ClarificationStatus.EXTENSION_REQUESTED
        if RequestStatus.RESPONDED in statuses:
            return ClarificationStatus.ANSWERED
        return ClarificationStatus.CLOSED

    def _evaluate(self, case_id: str, company_id: str, version: int, facts: dict[str, list]) -> Evaluation:
        findings: list[Finding] = []
        hypotheses: list[Hypothesis] = []
        scenarios: list[Scenario] = []
        tx_scores = []
        pending = any(p.status is ProposalStatus.AWAITING_HUMAN_REVIEW for p in facts["proposal"])
        for tx in facts["transaction"]:
            inputs = TransactionInputs(
                case_id=case_id, company_id=company_id, case_version=version, as_of=utcnow(), transaction=tx,
                invoice_observations=tuple(o for o in facts["invoice_observation"] if o.transaction_id == tx.transaction_id),
                payments=tuple(facts["payment"]), payment_allocations=tuple(facts["payment_allocation"]),
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
            if hasattr(self.checks, "test_hypotheses"):
                hypotheses += self.checks.test_hypotheses(inputs, tx_findings, pending_second_package=pending)
        index = self.checks.aggregate_company(tx_scores)
        evaluable = [s for s in tx_scores if s.evidence_coverage is not None]
        coverage = min((Decimal(s.evidence_coverage) for s in evaluable), default=None)
        unresolved_tx = {f.transaction_id for f in findings if f.status is FindingStatus.UNRESOLVED}
        contributions: dict[str, str] = {}
        for s in tx_scores:
            for fam, val in s.contributions.items():
                contributions[fam] = str(max(Decimal(val), Decimal(contributions.get(fam, "0"))))
        score = ScoreSnapshot(
            company_id=company_id, case_version=version, cutoff=utcnow(),
            method_id=tx_scores[0].method if tx_scores else "NONE", rules_version=getattr(self.checks, "calculation_version", "B"),
            review_index=index, evidence_coverage=str(coverage.quantize(Decimal("0.01"))) if coverage is not None else None,
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
        return self._evaluate(case_id, meta["company_id"], v, self._facts(case_id, v))

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
        return tuple(DocumentView(document=d, extraction=extractions.get(d.document_id),
                                  integrity=IntegrityReport(document_id=d.document_id, sha256=d.sha256,
                                                            limitations=("INTEGRITY_ADAPTER_NOT_RUN",)),
                                  case_version=version, mode=Mode.LIVE) for d in facts["document"])

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
                documents=tuple(dv for dv in self._doc_views(facts, v)
                                if dv.document.acquisition_channel.value != "SIMULATED_COUNTERPARTY_REFERENCE"),
                transactions=self._summaries(facts),
                projects=tuple(p for p in facts["project"] if p.company_id == company),
                context_claims=tuple(c for c in facts["context_claim"] if c.company_id == company),
                allocations=tuple(facts["allocation"]),
                pending_transcriptions=tuple(e for e in facts["extraction"] if e.status == "PROPOSED"),
                open_questions=open_q, inbox=published,
                responses=tuple(r for r in facts["response"] if r.author_actor_id == actor.actor_id),
                mode=Mode.LIVE, banner_fr=DEMO_BANNER_FR)
        ev = self._evaluate(case_id, company, v, facts)
        return OfficerCaseView(
            case_id=case_id, company_id=company, company_display_name=self._company_name(company), case_version=v,
            documents=self._doc_views(facts, v), transactions=self._summaries(facts),
            invoice_observations=tuple(facts["invoice_observation"]), payments=tuple(facts["payment"]),
            projects=tuple(facts["project"]), context_claims=tuple(facts["context_claim"]),
            quantity_references=tuple(facts["quantity_reference"]), allocations=tuple(facts["allocation"]),
            findings=ev.findings, hypotheses=ev.hypotheses, scenarios=ev.scenarios, score=ev.score,
            requests=tuple(facts["request"]), responses=tuple(facts["response"]), proposals=tuple(facts["proposal"]),
            mode=Mode.LIVE, mode_by_node={"checks": Mode.LIVE, "retrieval": Mode.NOT_RUN},
            banner_fr=DEMO_BANNER_FR)

    def list_queue(self, actor: Actor, cutoff, limit: int, cursor: str | None = None) -> QueuePage:
        actor = authorize(self.registry, actor, "list_queue")
        items = []
        for meta in self.store.list_cases():
            if meta["case_id"] not in actor.assigned_case_ids:
                continue
            ev = self.evaluate(meta["case_id"], meta["version"])
            items.append(QueueItem(
                case_id=meta["case_id"], company_id=meta["company_id"],
                company_display_name=self._company_name(meta["company_id"]), case_version=meta["version"],
                review_index=ev.score.review_index, evidence_coverage=ev.score.evidence_coverage,
                coverage_complete=ev.score.coverage_complete,
                active_finding_count=sum(f.status is FindingStatus.UNRESOLVED for f in ev.findings),
                clarification_status=ev.score.clarification_status, scope_note=ev.score.scope_note))
        items.sort(key=lambda i: (-(i.review_index if i.review_index is not None else -1), i.case_id))
        start = int(cursor or 0)
        page = items[start:start + limit]
        nxt = str(start + limit) if start + limit < len(items) else None
        return QueuePage(items=tuple(page), next_cursor=nxt,
                         cutoff=cutoff if isinstance(cutoff, datetime) else utcnow(), mode=Mode.LIVE)

    def get_history(self, actor: Actor, case_id: str) -> HistoryView:
        actor, _ = self._open(actor, case_id, "get_history")
        company = actor.role is Role.COMPANY
        internal = {"ANALYSIS_OFFICER", "EVIDENCE_REJECTED", "EXPORT"}
        events = tuple(e for e in self.store.events(case_id) if not (company and e.kind in internal))
        revisions = tuple(r.model_copy(update={"score_snapshot": None}) if company else r
                          for r in self.store.revisions(case_id))
        return HistoryView(case_id=case_id, audience=Audience.COMPANY if company else Audience.OFFICER,
                           revisions=revisions, events=events, mode=Mode.LIVE)

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
            project = Project(project_id=f"PRJ-{case_id[5:]}", company_id=company_id, label=label,
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
                        expected_version: int, request_id: str) -> DocumentView:
        actor, meta = self._open(actor, case_id, "upload_document")
        safe_name = Path(filename).name[:120]
        digest = hashlib.sha256(upload_bytes).hexdigest()
        ihash = self._input_hash(actor, "upload_document", [safe_name, media_type, digest, expected_version])
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
        # Extraction (possibly a model call) happens BEFORE the write transaction.
        extraction = self._extract(document, upload_bytes)
        if extraction is not None:
            document = document.model_copy(update={"extraction_status": extraction.status})
        _, path = self.store.save_original(upload_bytes, ".pdf")
        document = document.model_copy(update={"local_path": path})
        with self.store.write(case_id) as tx:
            if (prior := tx.find_receipt("upload_document", request_id, ihash)) is not None:
                return DocumentView.model_validate_json(prior)
            tx.require_version(expected_version)
            if any(d.document_id == doc_id for d in self.store.facts(case_id, "document", Document)):
                raise BousslaError(ErrorCode.INVALID_STATE, "Pièce identique déjà déposée dans ce dossier")
            tx.put("document", doc_id, document)
            if extraction is not None:
                tx.put("extraction", extraction.proposal_id, extraction)
            v = tx.commit_version(f"Pièce déposée : {safe_name}")
            tx.event("UPLOAD", actor.actor_id, f"Pièce déposée ({doc_id}) — original conservé, empreinte SHA-256", (doc_id,))
            view = DocumentView(document=document, extraction=extraction, case_version=v, mode=Mode.LIVE,
                                integrity=IntegrityReport(document_id=doc_id, sha256=digest,
                                                          limitations=("INTEGRITY_ADAPTER_NOT_RUN",)))
            tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="upload_document", case_id=case_id,
                                          actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                          result_hash=stable_hash(view.model_dump(mode="json"))), view)
        return view

    def _extract(self, document: Document, content: bytes) -> ExtractionProposal | None:
        if self.text_extractor is None or self.field_extractor is None:
            return None
        try:
            return self.field_extractor.extract_fields(self.text_extractor.extract_text(document, content))
        except BousslaError:
            raise
        except Exception:  # noqa: BLE001 - provider failure is never a finding; manual entry remains
            return None

    def confirm_transcription(self, actor: Actor, case_id: str, proposal_id: str, field_confirmations: dict[str, str],
                              expected_version: int, request_id: str) -> CompanyCaseView:
        actor, _ = self._open(actor, case_id, "confirm_transcription")
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
                tx.put("extraction", proposal_id, proposal.model_copy(update={"status": "CONFIRMED"}))
                tx.put("transcription_confirmation", proposal_id,
                       {"proposal_id": proposal_id, "fields": {str(k): str(v) for k, v in field_confirmations.items()},
                        "author_actor_id": actor.actor_id, "note": "Confirmation de transcription, pas d'authenticité"})
                v = tx.commit_version("Transcription confirmée par l'entreprise")
                tx.event("TRANSCRIPTION_CONFIRMED", actor.actor_id, "Transcription confirmée (confirmation ≠ authenticité)",
                         (proposal_id,))
                tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="confirm_transcription", case_id=case_id,
                                              actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                              result_hash=ihash), ReceiptNote(note="CONFIRMED", fact_ids=(proposal_id,)))
        return self.get_case(actor, case_id)

    def submit_context(self, actor: Actor, case_id: str, context_payload: dict, expected_version: int,
                       request_id: str) -> CompanyCaseView:
        actor, meta = self._open(actor, case_id, "submit_context")
        payload = {k: (str(v) if v is not None else None) for k, v in context_payload.items()}
        ihash = self._input_hash(actor, "submit_context", [payload, expected_version])
        try:
            category = PurposeCategory(payload.get("purpose_category") or "OTHER_OR_UNKNOWN")
        except ValueError:
            raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Catégorie d'usage inconnue") from None
        with self.store.write(case_id) as tx:
            if tx.find_receipt("submit_context", request_id, ihash) is None:
                tx.require_version(expected_version)
                projects = {p.project_id for p in self.store.facts(case_id, "project", Project)}
                txs = {t.transaction_id for t in self.store.facts(case_id, "transaction", Transaction)}
                if payload.get("project_id") and payload["project_id"] not in projects:
                    raise BousslaError(ErrorCode.CROSS_COMPANY, "Projet hors du périmètre de l'entreprise")
                if payload.get("transaction_id") and payload["transaction_id"] not in txs:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Transaction inconnue")
                claim = ContextClaim(
                    claim_id=f"CLAIM-{ihash[:8].upper()}", company_id=meta["company_id"],
                    transaction_id=payload.get("transaction_id"), project_id=payload.get("project_id"),
                    purpose_category=category, purpose_text=(payload.get("purpose_text") or "")[:2000],
                    beneficiary_type=payload.get("beneficiary_type") or "UNKNOWN",
                    planned_start=payload.get("planned_start"), planned_end=payload.get("planned_end"),
                    stage=payload.get("stage"), reported_stock_qty=payload.get("reported_stock_qty"),
                    author_actor_id=actor.actor_id, submitted_at=utcnow(),
                    supersedes_claim_id=payload.get("supersedes_claim_id"))
                tx.put("context_claim", claim.claim_id, claim)
                v = tx.commit_version("Contexte déclaré par l'entreprise (affirmation attribuée)")
                tx.event("CONTEXT", actor.actor_id, "Déclaration de contexte enregistrée (non vérifiée)", (claim.claim_id,))
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
        modes = {"checks": Mode.LIVE, "retrieval": Mode.NOT_RUN, "router": Mode.NOT_RUN,
                 "extractor": Mode.LIVE if facts["extraction"] else Mode.NOT_RUN}
        answered = self._answered_question_ids(facts)
        rounds = len({c.claim_id for c in facts["context_claim"] if c.purpose_text.startswith("[Q-")})
        question_ids, modes["planner"] = self._plan(ev, facts, answered, planner)
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
            questions=() if officer else tuple(QUESTIONS[q] for q in question_ids), question_round=rounds,
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
        answers = {str(k): str(v)[:2000] for k, v in answers.items()}
        unknown = set(answers) - set(QUESTIONS)
        if unknown:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Question inconnue", question_ids=sorted(unknown))
        ihash = self._input_hash(actor, "answer_questions", [analysis_id, answers, expected_version])
        with self.store.write(case_id) as tx:
            if tx.find_receipt("answer_questions", request_id, ihash) is None:
                tx.require_version(expected_version)
                ids = []
                for qid, text in sorted(answers.items()):
                    claim = ContextClaim(
                        claim_id=f"CLAIM-{stable_hash([ihash, qid])[:8].upper()}", company_id=meta["company_id"],
                        purpose_category=PurposeCategory(text) if qid == "Q-PURPOSE" and text in PurposeCategory.__members__
                        else PurposeCategory.OTHER_OR_UNKNOWN,
                        purpose_text=f"[{qid}] {text}", beneficiary_type="UNKNOWN", author_actor_id=actor.actor_id,
                        submitted_at=utcnow())
                    tx.put("context_claim", claim.claim_id, claim)
                    ids.append(claim.claim_id)
                v = tx.commit_version("Réponses de l'entreprise (affirmations attribuées)")
                tx.event("ANSWERS", actor.actor_id, "Réponses enregistrées comme affirmations de l'entreprise", tuple(ids))
                tx.save_receipt(ActionReceipt(idempotency_key=request_id, action="answer_questions", case_id=case_id,
                                              actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                              result_hash=ihash), ReceiptNote(note="ANSWERED", fact_ids=tuple(ids)))
        return self.start_analysis(actor, case_id, self.store.case_meta(case_id)["version"])

    # ------------------------------------------------------- clarification
    def prepare_clarification(self, actor: Actor, case_id: str, expected_version: int) -> ClarificationDraft:
        actor, meta = self._open(actor, case_id, "prepare_clarification")
        if expected_version != meta["version"]:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le")
        facts = self._facts(case_id, meta["version"])
        ev = self._evaluate(case_id, meta["company_id"], meta["version"], facts)
        qids = deterministic_plan(ev.findings, True, set()) or ["Q-SUPPORTING-DOC"]
        fact_ids = tuple(dict.fromkeys(
            r.source_record_id or r.document_id for f in ev.findings if f.status is FindingStatus.UNRESOLVED
            for r in f.evidence_refs if (r.source_record_id or r.document_id)))
        draft = ClarificationDraft(
            draft_id=f"DRAFT-{uuid.uuid4().hex[:8].upper()}", case_id=case_id, company_id=meta["company_id"],
            case_version=meta["version"], questions=tuple(QUESTIONS[q] for q in qids), fact_ids=fact_ids,
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
            v = tx.commit_version("Demande de précision publiée dans la boîte de démonstration")
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
        answers = {str(k): str(v)[:2000] for k, v in (payload.get("answers") or {}).items()}
        doc_ids = tuple(str(d) for d in payload.get("document_ids") or ())
        alloc = payload.get("allocation")
        ihash = self._input_hash(actor, "submit_response", [request_id, answers, doc_ids, alloc, expected_version])
        with self.store.write(case_id) as tx:
            if (prior := tx.find_receipt("submit_response", idempotency_key, ihash)) is not None:
                return ResponseView.model_validate_json(prior)
            tx.require_version(expected_version)
            rv = self.store.fact(case_id, "request", request_id, RequestView)
            if rv is None or rv.request.status is not RequestStatus.PUBLISHED_IN_DEMO:
                raise BousslaError(ErrorCode.INVALID_STATE, "Aucune demande publiée correspondante")
            if not set(answers) <= set(rv.request.question_ids):
                raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Réponse à une question non posée")
            docs = {d.document_id: d for d in self.store.facts(case_id, "document", Document)}
            for d in doc_ids:
                if d not in docs or docs[d].subject_company_id != meta["company_id"]:
                    raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Pièce inconnue ou hors périmètre")
            response = ClarificationResponse(
                response_id=f"RESP-{ihash[:8].upper()}", request_id=request_id, author_actor_id=actor.actor_id,
                document_ids=doc_ids, answers=answers, submitted_at=utcnow())
            tx.put("response", response.response_id, response)
            tx.put("request", request_id, rv.model_copy(update={
                "request": rv.request.model_copy(update={"status": RequestStatus.RESPONDED})}))
            proposal_ids: tuple[str, ...] = ()
            if alloc:
                proposal = self._build_proposal(case_id, meta["company_id"], expected_version + 1, alloc,
                                                response.response_id, doc_ids[0] if doc_ids else None)
                tx.put("proposal", proposal.proposal_id, proposal)
                proposal_ids = (proposal.proposal_id,)
            v = tx.commit_version("Réponse de l'entreprise reçue (proposition, pas une acceptation)")
            tx.event("RESPONSE", actor.actor_id, "Réponse reçue ; en attente de revue par l'agent",
                     (response.response_id, *proposal_ids))
            view = ResponseView(response=response, proposal_ids=proposal_ids, case_version=v, mode=Mode.LIVE)
            tx.save_receipt(ActionReceipt(idempotency_key=idempotency_key, action="submit_response", case_id=case_id,
                                          actor_id=actor.actor_id, input_hash=ihash, resulting_version=v,
                                          result_hash=stable_hash(view.model_dump(mode="json"))), view)
        return view

    def _build_proposal(self, case_id: str, company_id: str, version: int, alloc: dict, response_id: str,
                        document_id: str | None) -> EvidenceProposal:
        """Shape-check a proposed reallocation. Full scope/budget checks run again at acceptance."""
        tx_id, line_id = str(alloc.get("transaction_id", "")), str(alloc.get("line_id", ""))
        splits = {str(k): str(v) for k, v in (alloc.get("splits") or {}).items()}
        line = next((ln for o in self.store.facts(case_id, "invoice_observation", InvoiceObservation)
                     if o.transaction_id == tx_id and o.perspective is Perspective.BUYER_RECEIVED
                     for ln in o.lines if ln.line_id == line_id), None)
        if line is None or not splits:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Transaction ou ligne inconnue")
        current = {a.target_project_id: a for a in self.store.facts(case_id, "allocation", Allocation)
                   if a.transaction_id == tx_id and a.line_id == line_id and a.status is AllocationStatus.ACCEPTED}
        changes = []
        for project_id, qty in sorted(splits.items()):
            try:
                if Decimal(qty) < 0:
                    raise InvalidOperation
            except InvalidOperation:
                raise BousslaError(ErrorCode.INSUFFICIENT_INFORMATION, "Quantité invalide") from None
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
                new_allocations = self._apply_proposal(proposal, facts, meta["company_id"])
                for a in new_allocations:
                    old = next((x for x in facts["allocation"] if x.allocation_id == a.allocation_id), None)
                    if old != a:
                        tx.put("allocation", a.allocation_id, a)
            tx.put("proposal", proposal_id, proposal.model_copy(update={
                "status": ProposalStatus.ACCEPTED if accept else ProposalStatus.REJECTED}))
            after_facts = {**facts, "allocation": new_allocations,
                           "proposal": [p if p.proposal_id != proposal_id else p.model_copy(update={
                               "status": ProposalStatus.ACCEPTED if accept else ProposalStatus.REJECTED})
                                        for p in facts["proposal"]]}
            after = self._evaluate(case_id, meta["company_id"], previous + 1, after_facts)
            v = tx.commit_version(("Pièce acceptée dans ce dossier : " if accept else "Pièce rejetée : ")
                                  + (reason or proposal_id), (proposal_id,) if accept else (), score=after.score)
            tx.event("EVIDENCE_ACCEPTED" if accept else "EVIDENCE_REJECTED", actor.actor_id,
                     "Acceptée dans ce dossier par l'agent (pas une authentification)" if accept
                     else f"Rejetée par l'agent : {reason or '—'}", (proposal_id,))
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


def build_service(settings: Settings | None = None, seed: bool = True) -> BousslaAppService:
    """Default wiring: SQLite at CASE_DB_PATH, demo roster, B's checks or interim."""
    settings = settings or get_settings()
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    if seed:
        seed_demo_case(store)
    return BousslaAppService(store, settings=settings)
