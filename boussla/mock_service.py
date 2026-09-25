"""MOCK service fake — lane A. Every view it returns has ``mode=Mode.MOCK``.

Purpose: let D build the UI and B/C see the service shape before the real
SQLite/LangGraph service exists. It is in-memory, seeded from the synthetic
fixtures in ``docs/build_lock/fixtures/observed``. Findings and scores here are
HARD-CODED demo placeholders that mimic the shape of lane B's output; they are
not the deterministic checks and must never be presented as LIVE results.

It still enforces the same role/company scope, expected-version and
idempotency rules as the real service will, so UI code written against it
exercises the real error paths.

Usage::

    from boussla.mock_service import MockBousslaService, demo_actors
    svc = MockBousslaService()
    company, officer = demo_actors()["company"], demo_actors()["officer"]
    view = svc.get_case(company, "CASE-BRICKS-001")
"""
from __future__ import annotations

import csv
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from boussla.contracts import (
    ActionReceipt, Actor, Allocation, AllocationChange, AllocationStatus, AllocationTarget,
    AnalysisStatus, AnalysisView, Audience, CaseEvent, CaseRevision, ClarificationDraft,
    ClarificationRequest, ClarificationResponse, ClarificationStatus, CompanyCaseView,
    ContextClaim, Document, DocumentClass, DocumentView, Enterprise, ErrorCode,
    EvidenceProposal, EvidenceRef, Finding, FindingFamily, FindingStatus, HistoryView,
    Hypothesis, HypothesisStatus, IdentityMapping, InvoiceObservation, LocalDraftArtifact,
    Mode, OfficerCaseView, Payment, PaymentAllocation, PaymentStatus, Project,
    ProposalStatus, QuantityReference, Question, QueueItem, QueuePage, RequestStatus,
    RequestView, ResponseView, RevisionResult, Role, Scenario, ScoreSnapshot, Transaction,
    TransactionSummary, BousslaError,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "docs" / "build_lock" / "fixtures" / "observed"
TZ = timezone(timedelta(hours=1))
MOCK_BANNER_FR = (
    "Simulation de rôles locale — pas une authentification. "
    "Service FACTICE (MOCK) : constats et indices fixés pour la démo, pas des résultats calculés."
)
MOCK_CALC_VERSION = "MOCK-PLACEHOLDER-NOT-B-CHECKS"

QUESTIONS = {
    "Q-PROJECT-ALLOCATION": Question(
        question_id="Q-PROJECT-ALLOCATION",
        text_fr="Les 2 000 briques de la facture FAC-DEMO-001 sont-elles toutes affectées au lot P1 ? "
                "Sinon, indiquez les autres lots autorisés et les quantités.",
        answer_kind="QUANTITY",
        related_fact_ids=("ALLOC-P1-V1", "REF-P1"),
    ),
    "Q-SUPPORTING-DOC": Question(
        question_id="Q-SUPPORTING-DOC",
        text_fr="Pouvez-vous joindre la pièce d'affectation correspondante, si elle existe ?",
        answer_kind="DOCUMENT",
        related_fact_ids=("TX-001",),
    ),
}


def _now() -> datetime:
    return datetime.now(TZ)


def _load_json(name: str) -> list | dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_csv(name: str) -> list[dict]:
    with (FIXTURE_DIR / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def demo_actors() -> dict[str, Actor]:
    """Local role simulation actors matching the fixture seed."""
    return {
        "company": Actor(actor_id="DEMO-COMPANY-BAT", role=Role.COMPANY, company_id="DEMO-BAT"),
        "other_company": Actor(actor_id="DEMO-COMPANY-OTHER", role=Role.COMPANY, company_id="DEMO-OTHER"),
        "officer": Actor(actor_id="DEMO-OFFICER", role=Role.OFFICER, assigned_case_ids=("CASE-BRICKS-001",)),
        "operator": Actor(actor_id="DEMO-OPERATOR", role=Role.DEMO_OPERATOR),
    }


class MockBousslaService:
    """In-memory MOCK implementation of ``contracts.BousslaService``."""

    mode = Mode.MOCK

    def __init__(self) -> None:
        self.reset()

    # ------------------------------------------------------------------ setup
    def reset(self) -> None:
        seed = _load_json("case_seed.json")
        self.case_id: str = seed["case_id"]
        self.company_id: str = seed["company_id"]
        self.version: int = int(seed["case_version"])
        self.enterprises = {
            r["company_id"]: Enterprise(**{k: r[k] for k in ("company_id", "synthetic_mf", "display_name", "sector", "created_on")})
            for r in _load_csv("entreprises.csv")
        }
        doc_fields = set(Document.model_fields)
        self.documents = [
            Document(**{k: v for k, v in d.items() if k in doc_fields})
            for d in _load_json("documents.json")
            if d["document_id"] in seed["initial_document_ids"]
        ]
        self.observations = [InvoiceObservation(**o) for o in _load_json("invoice_observations.json")]
        self.transactions = [Transaction(**{k: v for k, v in t.items() if k != "synthetic"}) for t in _load_json("transactions.json")]
        self.payments = [Payment(**p) for p in _load_json("payments.json")]
        self.payment_allocations = [PaymentAllocation(**p) for p in _load_json("payment_allocations.json")]
        self.mappings = [IdentityMapping(**m) for m in _load_json("identity_mappings.json")]
        self.allocations = [Allocation(**a) for a in _load_json("allocations.json")]
        self.references = [QuantityReference(**r) for r in _load_json("quantity_references.json")]
        self.claims = [ContextClaim(**c) for c in _load_json("context_claims.json")]
        self.projects = [
            Project(project_id=r["project_id"], company_id=r["company_id"], label=r["label"],
                    project_type=r["project_type"], planned_start=r["planned_start"] or None,
                    planned_end=r["planned_end"] or None, reference_ids=(r["reference_id"],), status=r["status"])
            for r in _load_csv("projects.csv")
        ]
        self.drafts: dict[str, ClarificationDraft] = {}
        self.requests: dict[str, RequestView] = {}
        self.responses: list[ClarificationResponse] = []
        self.proposals: dict[str, EvidenceProposal] = {}
        self.receipts: dict[tuple[str, str], tuple[str, object]] = {}
        self.events: list[CaseEvent] = []
        self.revisions: list[CaseRevision] = []
        self.analysis_ran = False
        self._record_revision("Initialisation depuis les fixtures synthétiques", ())
        self._event("SEED", "DEMO-OPERATOR", "Dossier synthétique chargé (MOCK)")

    # ----------------------------------------------------------- scope rules
    def _require_case(self, case_id: str) -> None:
        if case_id != self.case_id:
            raise BousslaError(ErrorCode.NOT_FOUND, "Dossier inconnu")

    def _authorize(self, actor: Actor, case_id: str, *, roles: tuple[Role, ...]) -> None:
        self._require_case(case_id)
        if actor.role not in roles:
            raise BousslaError(ErrorCode.FORBIDDEN, "Action non autorisée pour ce rôle")
        if actor.role is Role.COMPANY and actor.company_id != self.company_id:
            raise BousslaError(ErrorCode.CROSS_COMPANY, "Ce dossier appartient à une autre entreprise")
        if actor.role is Role.OFFICER and case_id not in actor.assigned_case_ids:
            raise BousslaError(ErrorCode.FORBIDDEN, "Dossier non assigné")

    def _check_version(self, expected_version: int) -> None:
        if expected_version != self.version:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le",
                               expected=expected_version, current=self.version)

    def _idempotent(self, actor: Actor, action: str, key: str, payload: object):
        """Return stored result for an identical retry; raise on reused key."""
        stored = self.receipts.get((action, key))
        if stored is None:
            return None
        input_hash, result = stored
        if input_hash != _hash([actor.actor_id, payload]):
            raise BousslaError(ErrorCode.IDEMPOTENCY_CONFLICT, "Clé réutilisée avec un contenu différent")
        return result

    def _store_receipt(self, actor: Actor, action: str, key: str, payload: object, result: object) -> None:
        self.receipts[(action, key)] = (_hash([actor.actor_id, payload]), result)

    # --------------------------------------------------------- mock "checks"
    def _findings(self) -> list[Finding]:
        """HARD-CODED placeholder mimicking B's output shape. Not a calculation."""
        p1 = sum((Decimal(a.quantity) for a in self.allocations
                  if a.target_project_id == "P1" and a.status is AllocationStatus.ACCEPTED), Decimal(0))
        excess = max(Decimal(0), p1 - Decimal(1000))
        common = dict(case_id=self.case_id, company_id=self.company_id, transaction_id="TX-001",
                      calculation_version=MOCK_CALC_VERSION, case_version=self.version)
        return [
            Finding(finding_id="F-MOCK-CPTY", family=FindingFamily.COUNTERPARTY, status=FindingStatus.EXPLAINED,
                    severity="0", evidence_refs=(EvidenceRef(document_id="DOC-BUY-001"), EvidenceRef(document_id="DOC-SELL-001")),
                    reason_code="MOCK_OBSERVATIONS_AGREE", **common),
            Finding(finding_id="F-MOCK-SETTLE", family=FindingFamily.SETTLEMENT, status=FindingStatus.EXPLAINED,
                    severity="0", observed_difference_millimes=0, financial_basis="GROSS_PAYABLE_VS_SETTLED",
                    evidence_refs=(EvidenceRef(source_record_id="DOC-PAY-001"),), reason_code="MOCK_SETTLED_MATCHES", **common),
            Finding(finding_id="F-MOCK-QTY", family=FindingFamily.QUANTITY,
                    status=FindingStatus.UNRESOLVED if excess else FindingStatus.EXPLAINED,
                    severity="1" if excess else "0", quantity_difference=str(excess), unit="piece",
                    evidence_refs=(EvidenceRef(source_record_id="REF-P1"), EvidenceRef(source_record_id="ALLOC-P1-V1")),
                    missing_evidence_types=("ALLOCATION",) if excess else (),
                    reason_code="MOCK_ALLOCATION_EXCEEDS_REFERENCE" if excess else "MOCK_WITHIN_REFERENCE", **common),
        ]

    def _score(self) -> ScoreSnapshot:
        findings = self._findings()
        qty = next(f for f in findings if f.family is FindingFamily.QUANTITY)
        index = 40 if qty.status is FindingStatus.UNRESOLVED else 0
        return ScoreSnapshot(
            company_id=self.company_id, case_version=self.version, cutoff=_now(), method_id="MOCK",
            rules_version=MOCK_CALC_VERSION, review_index=index, evidence_coverage="100.00",
            coverage_complete=True, contributions={"COUNTERPARTY": "0", "SETTLEMENT": "0", "QUANTITY": str(index)},
            tested_families=tuple(FindingFamily), unknown_families=(),
            scope_note="MOCK — TX-001 uniquement ; valeurs fixées, pas calculées.",
            unresolved_distinct_transactions=1 if index else 0,
            clarification_status=self._clarification_status(),
        )

    def _hypotheses(self) -> list[Hypothesis]:
        base = dict(case_version=self.version, scope="TX-001/LINE-BUY-001")
        return [
            Hypothesis(hypothesis_id="H-SECOND-PACKAGE", statement_template_id="SECOND_AUTHORIZED_PACKAGE",
                       test_id="MOCK", status=HypothesisStatus.UNRESOLVED, missing_evidence_types=("ALLOCATION",), **base),
            Hypothesis(hypothesis_id="H-STOCK", statement_template_id="AUTHORIZED_STOCK",
                       test_id="MOCK", status=HypothesisStatus.UNRESOLVED, missing_evidence_types=("STOCK_RECORD",), **base),
            Hypothesis(hypothesis_id="H-RECORD-MISMATCH", statement_template_id="RECORD_MISMATCH",
                       test_id="MOCK", status=HypothesisStatus.UNRESOLVED, **base),
        ]

    def _scenarios(self) -> list[Scenario]:
        out = []
        for margin in ("0.00", "0.10"):
            bound = Decimal(1000) * (1 + Decimal(margin))
            p1 = sum((Decimal(a.quantity) for a in self.allocations if a.target_project_id == "P1"), Decimal(0))
            out.append(Scenario(scenario_id=f"S-MOCK-{margin}", label=f"Marge hypothétique {margin} (hypothèse fictive)",
                                inputs={"assigned": str(p1), "baseline": "1000", "margin": margin},
                                outputs={"hypothetical_bound": str(bound), "residual": str(max(Decimal(0), p1 - bound))}))
        return out

    def _clarification_status(self) -> ClarificationStatus:
        statuses = [rv.request.status for rv in self.requests.values()]
        if not statuses:
            return ClarificationStatus.NOT_REQUESTED
        if RequestStatus.PUBLISHED_IN_DEMO in statuses:
            return ClarificationStatus.PENDING
        if RequestStatus.RESPONDED in statuses:
            return ClarificationStatus.ANSWERED
        return ClarificationStatus.CLOSED

    # ------------------------------------------------------------ bookkeeping
    def _record_revision(self, reason: str, accepted: tuple[str, ...]) -> None:
        facts = [a.model_dump(mode="json") for a in self.allocations]
        self.revisions.append(CaseRevision(
            case_id=self.case_id, version=self.version,
            parent_version=self.revisions[-1].version if self.revisions else None,
            accepted_evidence_ids=accepted, fact_hash=_hash(facts), score_snapshot=None,
            created_at=_now(), reason=reason))

    def _event(self, kind: str, actor_id: str, summary: str, fact_ids: tuple[str, ...] = ()) -> None:
        self.events.append(CaseEvent(event_id=f"EV-{len(self.events) + 1:04d}", case_id=self.case_id, kind=kind,
                                     actor_id=actor_id, at=_now(), case_version=self.version, summary=summary,
                                     fact_ids=fact_ids))

    def _bump(self, reason: str, accepted: tuple[str, ...] = ()) -> None:
        self.version += 1
        # Any change invalidates unpublished drafts bound to the old version.
        self.drafts = {k: d for k, d in self.drafts.items() if d.case_version == self.version}
        self._record_revision(reason, accepted)

    def _summaries(self) -> tuple[TransactionSummary, ...]:
        out = []
        for tx in self.transactions:
            obs = [o for o in self.observations if o.transaction_id == tx.transaction_id]
            settled = sum(pa.allocated_millimes for pa in self.payment_allocations
                          if pa.transaction_id == tx.transaction_id
                          and any(p.payment_id == pa.payment_id and p.status is PaymentStatus.SETTLED for p in self.payments))
            origins = {o.origin_group_id for o in obs}
            seller = self.enterprises.get(tx.seller_company_id or "")
            out.append(TransactionSummary(
                transaction_id=tx.transaction_id, counterparty_company_id=tx.seller_company_id,
                counterparty_display_name=seller.display_name if seller else None,
                invoice_number=obs[0].invoice_number if obs else None, issued_on=obs[0].issued_on if obs else None,
                invoiced_gross_millimes=obs[0].gross_millimes if obs else None, settled_millimes=settled,
                observation_perspectives=tuple(o.perspective for o in obs),
                corroboration_status="DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY" if len(origins) > 1 else "COMMON_ORIGIN",
                project_id=tx.project_id))
        return tuple(out)

    def _doc_views(self) -> tuple[DocumentView, ...]:
        return tuple(DocumentView(document=d, case_version=self.version, mode=Mode.MOCK) for d in self.documents)

    # ================================================================ service
    def create_case(self, actor, company_id, project_payload, request_id):
        raise BousslaError(ErrorCode.INVALID_STATE, "MOCK : un seul dossier synthétique préchargé (CASE-BRICKS-001)")

    def upload_document(self, actor, case_id, upload_bytes, filename, media_type, expected_version, request_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY, Role.OFFICER))
        payload = [filename, media_type, hashlib.sha256(upload_bytes).hexdigest(), expected_version]
        if (prior := self._idempotent(actor, "upload_document", request_id, payload)) is not None:
            return prior
        self._check_version(expected_version)
        if media_type != "application/pdf" or not filename.lower().endswith(".pdf"):
            raise BousslaError(ErrorCode.UNSUPPORTED_FILE, "PDF uniquement")
        if len(upload_bytes) > 10 * 1024 * 1024:
            raise BousslaError(ErrorCode.LIMIT_EXCEEDED, "Fichier > 10 Mo")
        channel = "COMPANY_UPLOAD" if actor.role is Role.COMPANY else "OFFICER_UPLOAD"
        doc = Document(
            document_id=f"DOC-UP-{uuid.uuid4().hex[:8].upper()}", subject_company_id=self.company_id, case_id=case_id,
            original_filename=Path(filename).name, local_path="(MOCK: not persisted)",
            sha256=hashlib.sha256(upload_bytes).hexdigest(), media_type=media_type, received_at=_now(),
            uploader_actor_id=actor.actor_id, acquisition_channel=channel,
            origin_group_id=f"COMPANY-{self.company_id}" if actor.role is Role.COMPANY else "OFFICER",
            confidentiality_scope="CASE_PARTIES", processing_limitations=("MOCK_NOT_EXTRACTED",))
        self.documents.append(doc)
        self._bump(f"Pièce déposée : {doc.original_filename}")
        self._event("UPLOAD", actor.actor_id, f"Pièce déposée ({doc.document_id})", (doc.document_id,))
        view = DocumentView(document=doc, case_version=self.version, mode=Mode.MOCK)
        self._store_receipt(actor, "upload_document", request_id, payload, view)
        return view

    def confirm_transcription(self, actor, case_id, proposal_id, field_confirmations, expected_version, request_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY,))
        self._check_version(expected_version)
        self._event("TRANSCRIPTION_CONFIRMED", actor.actor_id,
                    "Transcription confirmée par l'entreprise (confirmation ≠ authenticité)", (proposal_id,))
        return self.get_case(actor, case_id)

    def submit_context(self, actor, case_id, context_payload, expected_version, request_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY,))
        payload = dict(context_payload)
        if self._idempotent(actor, "submit_context", request_id, payload) is not None:
            return self.get_case(actor, case_id)
        self._check_version(expected_version)
        claim = ContextClaim(
            claim_id=f"CLAIM-{uuid.uuid4().hex[:6].upper()}", company_id=self.company_id,
            transaction_id=payload.get("transaction_id"), project_id=payload.get("project_id"),
            purpose_category=payload.get("purpose_category", "OTHER_OR_UNKNOWN"),
            purpose_text=str(payload.get("purpose_text", "")), beneficiary_type=str(payload.get("beneficiary_type", "UNKNOWN")),
            planned_start=payload.get("planned_start"), planned_end=payload.get("planned_end"),
            stage=payload.get("stage"), author_actor_id=actor.actor_id, submitted_at=_now(),
            supersedes_claim_id=payload.get("supersedes_claim_id"))
        self.claims.append(claim)
        self._bump("Contexte déclaré par l'entreprise")
        self._event("CONTEXT", actor.actor_id, "Déclaration de contexte (affirmation attribuée)", (claim.claim_id,))
        self._store_receipt(actor, "submit_context", request_id, payload, True)
        return self.get_case(actor, case_id)

    def start_analysis(self, actor, case_id, expected_version):
        self._authorize(actor, case_id, roles=(Role.COMPANY, Role.OFFICER))
        self._check_version(expected_version)
        self.analysis_ran = True
        officer = actor.role is Role.OFFICER
        self._event("ANALYSIS", actor.actor_id, "Analyse MOCK exécutée (aucun modèle ni contrôle réel)")
        return AnalysisView(
            analysis_id=f"AN-MOCK-{self.version}", case_id=case_id, case_version=self.version,
            audience=Audience.OFFICER if officer else Audience.COMPANY,
            status=AnalysisStatus.COMPLETED if officer else AnalysisStatus.AWAITING_COMPANY_ANSWER,
            questions=() if officer else (QUESTIONS["Q-PROJECT-ALLOCATION"],), question_round=0 if officer else 1,
            findings=tuple(self._findings()) if officer else (), hypotheses=tuple(self._hypotheses()) if officer else (),
            scenarios=tuple(self._scenarios()) if officer else (), score=self._score() if officer else None,
            mode_by_node={n: Mode.MOCK for n in ("router", "extractor", "checks", "planner", "retrieval", "dossier")},
            mode=Mode.MOCK)

    def answer_questions(self, actor, case_id, analysis_id, answers, expected_version, request_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY,))
        self._check_version(expected_version)
        unknown = set(answers) - set(QUESTIONS)
        if unknown:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Question inconnue", question_ids=sorted(unknown))
        self._event("ANSWERS", actor.actor_id, "Réponses de l'entreprise enregistrées (affirmations attribuées)")
        return AnalysisView(analysis_id=analysis_id, case_id=case_id, case_version=self.version,
                            audience=Audience.COMPANY, status=AnalysisStatus.NEEDS_OFFICER_REVIEW,
                            question_round=2, mode_by_node={"planner": Mode.MOCK}, mode=Mode.MOCK)

    def get_case(self, actor, case_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY, Role.OFFICER))
        name = self.enterprises[self.company_id].display_name
        if actor.role is Role.COMPANY:
            published = tuple(rv for rv in self.requests.values() if rv.request.status is not RequestStatus.DRAFT)
            open_q = tuple(q for rv in published if rv.request.status is RequestStatus.PUBLISHED_IN_DEMO for q in rv.questions)
            return CompanyCaseView(
                case_id=case_id, company_id=self.company_id, company_display_name=name, case_version=self.version,
                documents=self._doc_views(), transactions=self._summaries(),
                projects=tuple(p for p in self.projects if p.company_id == self.company_id),
                context_claims=tuple(c for c in self.claims if c.company_id == self.company_id),
                allocations=tuple(self.allocations), open_questions=open_q, inbox=published,
                responses=tuple(self.responses), mode=Mode.MOCK, banner_fr=MOCK_BANNER_FR)
        return OfficerCaseView(
            case_id=case_id, company_id=self.company_id, company_display_name=name, case_version=self.version,
            documents=self._doc_views(), transactions=self._summaries(), invoice_observations=tuple(self.observations),
            payments=tuple(self.payments), projects=tuple(self.projects), context_claims=tuple(self.claims),
            quantity_references=tuple(self.references), allocations=tuple(self.allocations),
            findings=tuple(self._findings()), hypotheses=tuple(self._hypotheses()), scenarios=tuple(self._scenarios()),
            score=self._score(), requests=tuple(self.requests.values()), responses=tuple(self.responses),
            proposals=tuple(self.proposals.values()),
            mode=Mode.MOCK, mode_by_node={"checks": Mode.MOCK, "retrieval": Mode.NOT_RUN}, banner_fr=MOCK_BANNER_FR)

    def list_queue(self, actor, cutoff, limit, cursor=None):
        if actor.role is not Role.OFFICER:
            raise BousslaError(ErrorCode.FORBIDDEN, "File de revue réservée aux agents")
        items = []
        if self.case_id in actor.assigned_case_ids:
            score = self._score()
            items.append(QueueItem(
                case_id=self.case_id, company_id=self.company_id,
                company_display_name=self.enterprises[self.company_id].display_name, case_version=self.version,
                review_index=score.review_index, evidence_coverage=score.evidence_coverage,
                coverage_complete=score.coverage_complete,
                active_finding_count=sum(f.status is FindingStatus.UNRESOLVED for f in self._findings()),
                clarification_status=score.clarification_status, scope_note=score.scope_note))
        return QueuePage(items=tuple(items[:limit]), cutoff=cutoff if isinstance(cutoff, datetime) else _now(), mode=Mode.MOCK)

    def prepare_clarification(self, actor, case_id, expected_version):
        self._authorize(actor, case_id, roles=(Role.OFFICER,))
        self._check_version(expected_version)
        draft = ClarificationDraft(
            draft_id=f"DRAFT-{uuid.uuid4().hex[:6].upper()}", case_id=case_id, company_id=self.company_id,
            case_version=self.version, questions=(QUESTIONS["Q-PROJECT-ALLOCATION"], QUESTIONS["Q-SUPPORTING-DOC"]),
            fact_ids=("TX-001", "ALLOC-P1-V1", "REF-P1"), allowed_document_types=(DocumentClass.ALLOCATION_RESPONSE,),
            target_response_at=_now() + timedelta(days=7),
            text_fr="Demande de précision neutre (démo locale, aucun envoi externe) : merci de préciser l'affectation "
                    "des quantités de la facture FAC-DEMO-001. Date cible indicative de démonstration, pas un délai légal.",
            mode=Mode.TEMPLATE)
        self.drafts[draft.draft_id] = draft
        return draft

    def publish_clarification(self, actor, case_id, draft_id, expected_version, request_id):
        self._authorize(actor, case_id, roles=(Role.OFFICER,))
        payload = [draft_id, expected_version]
        if (prior := self._idempotent(actor, "publish_clarification", request_id, payload)) is not None:
            return prior
        self._check_version(expected_version)
        draft = self.drafts.get(draft_id)
        if draft is None or draft.case_version != self.version:
            raise BousslaError(ErrorCode.STALE_REVISION, "Brouillon inconnu ou lié à une ancienne version")
        now = _now()
        req = ClarificationRequest(
            request_id=f"REQ-{uuid.uuid4().hex[:6].upper()}", case_id=case_id, company_id=self.company_id,
            case_version=self.version, fact_ids=draft.fact_ids, question_ids=tuple(q.question_id for q in draft.questions),
            allowed_document_types=draft.allowed_document_types, target_response_at=draft.target_response_at,
            status=RequestStatus.PUBLISHED_IN_DEMO, approved_by=actor.actor_id, published_at=now, available_in_inbox_at=now)
        view = RequestView(request=req, questions=draft.questions, text_fr=draft.text_fr, mode=Mode.MOCK)
        self.requests[req.request_id] = view
        del self.drafts[draft_id]
        self._bump("Demande de précision publiée dans la boîte de démo")
        self._event("REQUEST_PUBLISHED", actor.actor_id, "Demande publiée localement (aucun e-mail/SMS)", (req.request_id,))
        self._store_receipt(actor, "publish_clarification", request_id, payload, view)
        return view

    def submit_response(self, actor, case_id, request_id, payload, expected_version, idempotency_key):
        """payload: {"answers": {qid: text}, "document_ids": [...],
        "allocation": {"P1": "1000", "P2": "1000"}} — allocation is optional."""
        self._authorize(actor, case_id, roles=(Role.COMPANY,))
        key_payload = [request_id, payload, expected_version]
        if (prior := self._idempotent(actor, "submit_response", idempotency_key, key_payload)) is not None:
            return prior
        self._check_version(expected_version)
        rv = self.requests.get(request_id)
        if rv is None or rv.request.status is not RequestStatus.PUBLISHED_IN_DEMO:
            raise BousslaError(ErrorCode.INVALID_STATE, "Aucune demande publiée correspondante")
        known_docs = {d.document_id for d in self.documents}
        doc_ids = tuple(payload.get("document_ids", ()))
        if not set(doc_ids) <= known_docs:
            raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Pièce inconnue")
        resp = ClarificationResponse(
            response_id=f"RESP-{uuid.uuid4().hex[:6].upper()}", request_id=request_id, author_actor_id=actor.actor_id,
            document_ids=doc_ids, answers={str(k): str(v) for k, v in payload.get("answers", {}).items()}, submitted_at=_now())
        self.responses.append(resp)
        self.requests[request_id] = rv.model_copy(update={"request": rv.request.model_copy(update={"status": RequestStatus.RESPONDED})})
        proposal_ids: tuple[str, ...] = ()
        if alloc := payload.get("allocation"):
            prop = EvidenceProposal(
                proposal_id=f"PROP-{uuid.uuid4().hex[:6].upper()}", case_id=case_id, expected_version=self.version + 1,
                source_document_id=doc_ids[0] if doc_ids else None, source_response_id=resp.response_id,
                transaction_id="TX-001", line_id="LINE-BUY-001", unit="piece", budget_quantity="2000",
                changes=tuple(
                    AllocationChange(action="REPLACE" if pid == "P1" else "CREATE",
                                     allocation_id="ALLOC-P1-V1" if pid == "P1" else f"ALLOC-{pid}-V{self.version + 2}",
                                     target_project_id=pid, old_quantity="2000" if pid == "P1" else None, new_quantity=str(q))
                    for pid, q in alloc.items()),
                status=ProposalStatus.AWAITING_HUMAN_REVIEW)
            self.proposals[prop.proposal_id] = prop
            proposal_ids = (prop.proposal_id,)
        self._bump("Réponse de l'entreprise reçue (proposition, pas une acceptation)")
        self._event("RESPONSE", actor.actor_id, "Réponse reçue ; en attente de revue", (resp.response_id, *proposal_ids))
        view = ResponseView(response=resp, proposal_ids=proposal_ids, case_version=self.version, mode=Mode.MOCK)
        self._store_receipt(actor, "submit_response", idempotency_key, key_payload, view)
        return view

    def _decide(self, actor, case_id, proposal_id, expected_version, idempotency_key, accept: bool, reason: str | None):
        self._authorize(actor, case_id, roles=(Role.OFFICER,))
        action = "accept_evidence" if accept else "reject_evidence"
        payload = [proposal_id, expected_version, reason]
        # Identical authorized retry returns the stored outcome BEFORE the version check.
        if (prior := self._idempotent(actor, action, idempotency_key, payload)) is not None:
            return prior.model_copy(update={"replayed": True})
        self._check_version(expected_version)
        prop = self.proposals.get(proposal_id)
        if prop is None:
            raise BousslaError(ErrorCode.NOT_FOUND, "Proposition inconnue")
        if prop.status is not ProposalStatus.AWAITING_HUMAN_REVIEW:
            raise BousslaError(ErrorCode.DUPLICATE_ACCEPTANCE, "Proposition déjà traitée")
        before_alloc, before_findings, before_score = tuple(self.allocations), tuple(self._findings()), self._score()
        previous = self.version
        if accept:
            total = sum((Decimal(c.new_quantity) for c in prop.changes), Decimal(0))
            if total > Decimal(prop.budget_quantity):
                raise BousslaError(ErrorCode.ALLOCATION_OVERFLOW, "Quantités affectées > quantité facturée")
            by_id = {a.allocation_id: a for a in self.allocations}
            for ch in prop.changes:
                base = by_id.get(ch.allocation_id) or by_id["ALLOC-P1-V1"]
                by_id[ch.allocation_id] = base.model_copy(update={
                    "allocation_id": ch.allocation_id, "target_project_id": ch.target_project_id,
                    "target_type": AllocationTarget(ch.target_type), "quantity": ch.new_quantity,
                    "source_refs": tuple(x for x in (prop.source_document_id, prop.source_response_id) if x),
                    "status": AllocationStatus.ACCEPTED, "effective_on": date.today()})
            self.allocations = list(by_id.values())
        self.proposals[proposal_id] = prop.model_copy(update={"status": ProposalStatus.ACCEPTED if accept else ProposalStatus.REJECTED})
        self._bump(("Pièce acceptée : " if accept else "Pièce rejetée : ") + (reason or proposal_id),
                   (proposal_id,) if accept else ())
        self._event("EVIDENCE_ACCEPTED" if accept else "EVIDENCE_REJECTED", actor.actor_id,
                    "Décision de l'agent sur la proposition (acceptée dans ce dossier, pas authentifiée)", (proposal_id,))
        receipt = ActionReceipt(idempotency_key=idempotency_key, action=action, case_id=case_id, actor_id=actor.actor_id,
                                input_hash=_hash([actor.actor_id, payload]), resulting_version=self.version,
                                result_hash=_hash([a.model_dump(mode="json") for a in self.allocations]))
        result = RevisionResult(
            case_id=case_id, outcome="ACCEPTED" if accept else "REJECTED", previous_version=previous,
            new_version=self.version, receipt=receipt, allocations_before=before_alloc,
            allocations_after=tuple(self.allocations), findings_before=before_findings,
            findings_after=tuple(self._findings()), score_before=before_score, score_after=self._score(), mode=Mode.MOCK)
        self._store_receipt(actor, action, idempotency_key, payload, result)
        return result

    def accept_evidence(self, actor, case_id, proposal_id, expected_version, idempotency_key):
        return self._decide(actor, case_id, proposal_id, expected_version, idempotency_key, True, None)

    def reject_evidence(self, actor, case_id, proposal_id, expected_version, reason, idempotency_key):
        return self._decide(actor, case_id, proposal_id, expected_version, idempotency_key, False, reason)

    def get_history(self, actor, case_id):
        self._authorize(actor, case_id, roles=(Role.COMPANY, Role.OFFICER))
        company = actor.role is Role.COMPANY
        internal = {"ANALYSIS", "EVIDENCE_REJECTED"}
        events = tuple(e for e in self.events if not (company and e.kind in internal))
        return HistoryView(case_id=case_id, audience=Audience.COMPANY if company else Audience.OFFICER,
                           revisions=tuple(self.revisions), events=events, mode=Mode.MOCK)

    def export_dossier(self, actor, case_id, audience, expected_version):
        self._authorize(actor, case_id, roles=(Role.OFFICER,))
        self._check_version(expected_version)
        audience = Audience(audience)
        lines = [f"# Dossier {case_id} — version {self.version}", "", "_Brouillon local MOCK — non officiel._", ""]
        if audience is Audience.OFFICER:
            lines += [f"- {f.family.value}: {f.status.value} ({f.reason_code})" for f in self._findings()]
        else:
            lines += ["Questions publiées :"] + [f"- {q.text_fr}" for rv in self.requests.values() for q in rv.questions]
        return LocalDraftArtifact(
            artifact_id=f"ART-{uuid.uuid4().hex[:6].upper()}", case_id=case_id, audience=audience, case_version=self.version,
            filename=f"{case_id}_v{self.version}_{audience.value.lower()}_MOCK.md", content_markdown="\n".join(lines),
            generated_at=_now(), mode=Mode.MOCK,
            disclaimer_fr="Brouillon de démonstration ; aucune valeur juridique ; aucune notification envoyée.")
