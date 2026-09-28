"""Acceptance tests for the real SQLite-backed service (handoff §Acceptance tests)."""
import pytest

from boussla.config import FIXTURE_ROOT, Settings
from boussla.contracts import (
    Actor, AllocationStatus, AnalysisStatus, Audience, BousslaError, BousslaService, CompanyCaseView,
    ErrorCode, FindingFamily, FindingStatus, HypothesisStatus, Mode, OfficerCaseView, ProposalStatus,
    RequestStatus, Role,
)
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import BousslaAppService
from boussla.store import CaseStore

CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


@pytest.fixture
def svc(tmp_path):
    settings = Settings(case_db_path=tmp_path / "c.sqlite", upload_dir=tmp_path / "up")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    return BousslaAppService(store, ActorRegistry.demo(), settings=settings)


@pytest.fixture
def actors(svc):
    r = svc.registry.actors
    return r["DEMO-COMPANY-BAT"], r["DEMO-OFFICER"], r["DEMO-COMPANY-OTHER"]


def code(fn):
    with pytest.raises(BousslaError) as e:
        fn()
    return e.value.code


def ver(svc):
    return svc.store.case_meta(CASE)["version"]


def qty(findings):
    return next(f for f in findings if f.family is FindingFamily.QUANTITY)


def to_proposal(svc, actors, splits=None):
    co, off, _ = actors
    draft = svc.prepare_clarification(off, CASE, ver(svc))
    req = svc.publish_clarification(off, CASE, draft.draft_id, ver(svc), "pub-1")
    doc = svc.upload_document(co, CASE, PDF, "affectation_P2.pdf", "application/pdf", ver(svc), "up-1")
    resp = svc.submit_response(co, CASE, req.request.request_id, {
        "answers": {"Q-PROJECT-ALLOCATION": "1000 unités P1, 1000 unités P2"},
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001",
                       "splits": splits or {"P1": "1000", "P2": "1000"}}}, ver(svc), "resp-1")
    return resp


def test_satisfies_protocol(svc):
    assert isinstance(svc, BousslaService)


def test_initial_views(svc, actors):
    co, off, _ = actors
    c, o = svc.get_case(co, CASE), svc.get_case(off, CASE)
    assert isinstance(c, CompanyCaseView) and isinstance(o, OfficerCaseView) and o.mode is Mode.LIVE
    assert qty(o.findings).status is FindingStatus.UNRESOLVED and o.score.review_index == 40
    tx = o.transactions[0]
    assert tx.invoiced_gross_millimes == 4760000 and tx.settled_millimes == 4760000
    # company does not see the simulated counterpart record
    assert "DOC-SELL-001" not in {d.document.document_id for d in c.documents}


def test_wrong_company_forbidden_before_any_read(svc, actors):
    assert code(lambda: svc.get_case(actors[2], CASE)) is ErrorCode.CROSS_COMPANY
    assert code(lambda: svc.start_analysis(actors[2], CASE, 1)) is ErrorCode.CROSS_COMPANY


def test_forged_actor_rejected(svc):
    forged = Actor(actor_id="DEMO-COMPANY-BAT", role=Role.OFFICER, assigned_case_ids=(CASE,))
    assert code(lambda: svc.get_case(forged, CASE)) is ErrorCode.FORBIDDEN


def test_company_cannot_approve_its_evidence(svc, actors):
    resp = to_proposal(svc, actors)
    assert code(lambda: svc.accept_evidence(actors[0], CASE, resp.proposal_ids[0], ver(svc), "k")) is ErrorCode.FORBIDDEN


def test_full_loop_recalculates_exactly_once(svc, actors):
    co, off, _ = actors
    resp = to_proposal(svc, actors)
    c = svc.get_case(co, CASE)
    assert c.inbox[0].request.status is RequestStatus.RESPONDED
    before_v = ver(svc)
    r = svc.accept_evidence(off, CASE, resp.proposal_ids[0], before_v, "acc-1")
    assert r.outcome == "ACCEPTED" and r.new_version == before_v + 1
    assert {a.target_project_id: a.quantity for a in r.allocations_after} == {"P1": "1000", "P2": "1000"}
    assert r.score_before.review_index == 20 and r.score_after.review_index == 0
    assert r.score_before.raw_review_index == 40
    assert qty(r.findings_after).status is FindingStatus.EXPLAINED
    o = svc.get_case(off, CASE)
    assert o.score.review_index == 0 and o.proposals[0].status is ProposalStatus.ACCEPTED
    assert {h.hypothesis_id: h.status for h in o.hypotheses}["H-SECOND-PACKAGE"] is HypothesisStatus.SUPPORTED
    # history keeps the old allocation (nothing destroyed)
    old = svc.store.facts(CASE, "allocation", type(r.allocations_before[0]), version=before_v)
    assert [a.quantity for a in old] == ["2000"]


def test_duplicate_exact_action_returns_prior_outcome(svc, actors):
    off = actors[1]
    resp = to_proposal(svc, actors)
    v = ver(svc)
    r1 = svc.accept_evidence(off, CASE, resp.proposal_ids[0], v, "acc-1")
    r2 = svc.accept_evidence(off, CASE, resp.proposal_ids[0], v, "acc-1")  # stale version, same key
    assert r2.replayed and r2.new_version == r1.new_version and ver(svc) == r1.new_version
    assert len(svc.store.revisions(CASE)) == r1.new_version


def test_same_key_different_payload_fails(svc, actors):
    co, off, _ = actors
    svc.submit_context(co, CASE, {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "a"}, ver(svc), "ctx")
    assert code(lambda: svc.submit_context(co, CASE, {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "b"},
                                           ver(svc), "ctx")) is ErrorCode.IDEMPOTENCY_CONFLICT


def test_stale_approval_fails(svc, actors):
    resp = to_proposal(svc, actors)
    assert code(lambda: svc.accept_evidence(actors[1], CASE, resp.proposal_ids[0], ver(svc) - 1, "new")) is ErrorCode.STALE_REVISION


def test_second_acceptance_new_key_rejected(svc, actors):
    resp = to_proposal(svc, actors)
    svc.accept_evidence(actors[1], CASE, resp.proposal_ids[0], ver(svc), "a1")
    assert code(lambda: svc.accept_evidence(actors[1], CASE, resp.proposal_ids[0], ver(svc), "a2")) is ErrorCode.DUPLICATE_ACCEPTANCE


def test_record_change_invalidates_old_draft(svc, actors):
    co, off, _ = actors
    draft = svc.prepare_clarification(off, CASE, ver(svc))
    svc.submit_context(co, CASE, {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "maj"}, ver(svc), "c")
    snapshot = svc.store.revisions(CASE)[-1].score_snapshot
    assert snapshot is not None and snapshot.case_version == ver(svc)
    assert snapshot.calculated_at is not None and snapshot.rules_version and snapshot.engine_version
    assert code(lambda: svc.publish_clarification(off, CASE, draft.draft_id, ver(svc), "p")) is ErrorCode.STALE_REVISION


def test_overflow_leaves_facts_unchanged(svc, actors):
    resp = to_proposal(svc, actors, splits={"P1": "1500", "P2": "1000"})
    v = ver(svc)
    assert code(lambda: svc.accept_evidence(actors[1], CASE, resp.proposal_ids[0], v, "a")) is ErrorCode.ALLOCATION_OVERFLOW
    assert ver(svc) == v and svc.get_case(actors[1], CASE).proposals[0].status is ProposalStatus.AWAITING_HUMAN_REVIEW


def test_cross_company_project_rejected(svc, actors):
    resp = to_proposal(svc, actors, splits={"P1": "1000", "P-OTHER": "1000"})
    assert code(lambda: svc.accept_evidence(actors[1], CASE, resp.proposal_ids[0], ver(svc), "a")) is ErrorCode.CROSS_COMPANY


def test_reject_keeps_allocations(svc, actors):
    resp = to_proposal(svc, actors)
    r = svc.reject_evidence(actors[1], CASE, resp.proposal_ids[0], ver(svc), "pièce illisible", "rej")
    assert r.outcome == "REJECTED" and r.score_after.review_index == 40
    assert [a.quantity for a in r.allocations_after] == ["2000"]


def test_request_is_local_demo_only(svc, actors):
    off = actors[1]
    d = svc.prepare_clarification(off, CASE, ver(svc))
    req = svc.publish_clarification(off, CASE, d.draft_id, ver(svc), "p")
    assert req.request.target_kind == "DEMO_SERVICE_TARGET" and req.request.status is RequestStatus.PUBLISHED_IN_DEMO
    snapshot = svc.store.revisions(CASE)[-1].score_snapshot
    assert snapshot is not None and snapshot.case_version == ver(svc)
    assert snapshot.calculated_at is not None and snapshot.rules_version and snapshot.engine_version
    assert "aucun envoi externe" in req.text_fr and "pas un délai légal" in req.text_fr


def test_company_analysis_questions_without_internal_data(svc, actors):
    an = svc.start_analysis(actors[0], CASE, ver(svc))
    assert an.status is AnalysisStatus.AWAITING_COMPANY_ANSWER and an.questions
    assert an.findings == () and an.score is None
    after = svc.answer_questions(actors[0], CASE, an.analysis_id, {an.questions[0].question_id: "réponse"}, ver(svc), "ans")
    assert an.questions[0].question_id not in {q.question_id for q in after.questions}
    snapshot = svc.store.revisions(CASE)[-1].score_snapshot
    assert snapshot is not None and snapshot.case_version == ver(svc)
    assert snapshot.calculated_at is not None and snapshot.rules_version and snapshot.engine_version


def test_upload_validation(svc, actors):
    co = actors[0]
    v = ver(svc)
    assert code(lambda: svc.upload_document(co, CASE, b"MZ...", "x.pdf", "application/pdf", v, "u")) is ErrorCode.UNSUPPORTED_FILE
    assert code(lambda: svc.upload_document(co, CASE, b"%PDF-broken", "x.pdf", "application/pdf", v, "u2")) is ErrorCode.UNSUPPORTED_FILE
    dv = svc.upload_document(co, CASE, PDF, "../../evil.pdf", "application/pdf", v, "u3")
    assert dv.document.original_filename == "evil.pdf" and dv.document.origin_group_id == "COMPANY-DEMO-BAT"
    again = svc.upload_document(co, CASE, PDF, "../../evil.pdf", "application/pdf", v, "u3")
    assert again == dv and ver(svc) == v + 1


def test_history_scoped_and_export(svc, actors):
    co, off, _ = actors
    to_proposal(svc, actors)
    svc.start_analysis(off, CASE, ver(svc))
    assert "ANALYSIS_OFFICER" not in {e.kind for e in svc.get_history(co, CASE).events}
    assert all(r.score_snapshot is None for r in svc.get_history(co, CASE).revisions)
    art = svc.export_dossier(off, CASE, Audience.COMPANY, ver(svc))
    assert "QUANTITY" not in art.content_markdown and "Indice" not in art.content_markdown
    assert code(lambda: svc.export_dossier(co, CASE, Audience.COMPANY, ver(svc))) is ErrorCode.FORBIDDEN


def test_queue(svc, actors):
    page = svc.list_queue(actors[1], None, 10)
    assert page.items[0].case_id == CASE and page.items[0].review_index == 40 and page.items[0].active_finding_count == 1


def test_create_case_scoped(svc, actors):
    co, _, other = actors
    view = svc.create_case(co, "DEMO-BAT", {"label": "Nouveau lot"}, "new-1")
    assert view.company_id == "DEMO-BAT" and view.case_version == 1
    assert svc.create_case(co, "DEMO-BAT", {"label": "Nouveau lot"}, "new-1").case_id == view.case_id
    assert code(lambda: svc.create_case(co, "DEMO-OTHER", {"label": "x"}, "n")) is ErrorCode.CROSS_COMPANY


class _Text:
    def extract_text(self, document, content):
        from boussla.contracts import DocumentText, PageText
        return DocumentText(document_id=document.document_id, pages=(PageText(page=1, text="Facture X"),), status="OK")


class _Fields:
    def extract_fields(self, text):
        from boussla.contracts import CandidateField, EvidenceRef, ExtractionProposal
        return ExtractionProposal(proposal_id=f"EXT-{text.document_id}", document_id=text.document_id,
                                  candidates=(CandidateField(field_name="invoice_number", raw_value="X", normalized_value="X",
                                      evidence_refs=(EvidenceRef(document_id=text.document_id,page=1,
                                          exact_text="X",field_name="invoice_number"),)),),
                                  mode=Mode.MANUAL, prompt_version="t")


class _Integrity:
    def inspect(self, document, content):
        from boussla.contracts import IntegrityReport
        return IntegrityReport(document_id=document.document_id, sha256=document.sha256, signature_status="UNSIGNED")


class _Broken:
    def inspect(self, document, content):
        raise RuntimeError("boom")

    def extract_text(self, document, content):
        raise RuntimeError("boom")


def _svc_with(tmp_path, **adapters):
    settings = Settings(case_db_path=tmp_path / "a.sqlite", upload_dir=tmp_path / "u")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    return BousslaAppService(store, ActorRegistry.demo(), settings=settings, **adapters)


def test_injected_adapters_run_on_upload_and_confirm(tmp_path):
    svc = _svc_with(tmp_path, text_extractor=_Text(), field_extractor=_Fields(), integrity_inspector=_Integrity())
    co = svc.registry.actors["DEMO-COMPANY-BAT"]
    dv = svc.upload_document(co, CASE, PDF, "f.pdf", "application/pdf", 1, "u")
    assert dv.integrity.signature_status == "UNSIGNED" and dv.extraction.proposal_id.startswith("EXT-")
    view = svc.get_case(co, CASE)
    uploaded = next(d for d in view.documents if d.document.document_id == dv.document.document_id)
    assert view.pending_transcriptions and uploaded.integrity.signature_status == "UNSIGNED"
    after = svc.confirm_transcription(co, CASE, dv.extraction.proposal_id, {"invoice_number": "X"}, 2, "c")
    assert after.case_version == 3 and not after.pending_transcriptions
    with pytest.raises(BousslaError) as e:
        svc.confirm_transcription(co, CASE, dv.extraction.proposal_id, {"iban": "x"}, 3, "c2")
    assert e.value.code is ErrorCode.INVALID_EVIDENCE_REFERENCE


def test_adapter_failures_degrade_to_manual(tmp_path):
    svc = _svc_with(tmp_path, text_extractor=_Broken(), field_extractor=_Fields(), integrity_inspector=_Broken())
    dv = svc.upload_document(svc.registry.actors["DEMO-COMPANY-BAT"], CASE, PDF, "f.pdf", "application/pdf", 1, "u")
    assert dv.extraction is None and "INTEGRITY_ADAPTER_NOT_RUN" in dv.integrity.limitations


def test_engine_discovery_prefers_lane_b(monkeypatch):
    import sys
    import types
    from boussla import interim_checks
    mod = types.ModuleType("boussla.checks")

    class ChecksEngineV4(interim_checks.InterimChecks):
        pass
    mod.ChecksEngineV4 = ChecksEngineV4
    monkeypatch.setitem(sys.modules, "boussla.checks", mod)
    monkeypatch.setattr(interim_checks.importlib.util, "find_spec", lambda name: object())
    import boussla
    monkeypatch.setattr(boussla, "checks", mod, raising=False)
    assert type(interim_checks.get_checks_engine()).__name__ == "ChecksEngineV4"


def test_upload_revision_hash_covers_every_fact_of_that_version(svc, actors):
    """The recorded fact_hash of a version must match the facts as of that version
    (regression: the integrity fact was written after commit_version)."""
    svc.upload_document(actors[0], CASE, PDF, "a.pdf", "application/pdf", ver(svc), "u")
    v = ver(svc)
    recorded = svc.store.revisions(CASE)[-1]
    with svc.store.write(CASE) as tx:
        actual = tx._current_fact_hash(v)
    assert recorded.version == v and recorded.fact_hash == actual


@pytest.mark.parametrize("payload", [
    {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "d", "planned_start": "not-a-date"},
    {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "d", "planned_start": "2026-12-01", "planned_end": "2026-01-01"},
    {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "d", "reported_stock_qty": "beaucoup"},
])
def test_invalid_context_is_a_typed_error_and_writes_nothing(svc, actors, payload):
    v = ver(svc)
    assert code(lambda: svc.submit_context(actors[0], CASE, payload, v, "bad")) is ErrorCode.INSUFFICIENT_INFORMATION
    assert ver(svc) == v


def test_invalid_project_dates_on_create_case(svc, actors):
    for payload in ({"label": "x", "planned_start": "32/13/2026"},
                    {"label": "x", "planned_start": "2026-12-01", "planned_end": "2026-01-01"}):
        assert code(lambda: svc.create_case(actors[0], "DEMO-BAT", payload, str(payload))) is ErrorCode.INSUFFICIENT_INFORMATION


@pytest.mark.parametrize("cursor", ["abc", "-1", "1.5"])
def test_invalid_queue_cursor_is_a_typed_error(svc, actors, cursor):
    assert code(lambda: svc.list_queue(actors[1], None, 10, cursor)) is ErrorCode.INSUFFICIENT_INFORMATION


def test_queue_pagination(svc, actors):
    page = svc.list_queue(actors[1], None, 10, "0")
    assert len(page.items) == 1 and page.next_cursor is None
    assert svc.list_queue(actors[1], None, 10, "5").items == ()


def test_question_rounds_count_answer_batches_not_answered_questions(svc, actors):
    """Answering three questions in ONE round is one round, not three (max rounds = 2)."""
    co = actors[0]
    first = svc.start_analysis(co, CASE, ver(svc))
    assert len(first.questions) == 3 and first.question_round == 0
    after = svc.answer_questions(co, CASE, first.analysis_id, {q.question_id: "réponse" for q in first.questions},
                                 ver(svc), "round-1")
    assert after.question_round == 1


def test_extractor_cannot_introduce_a_value_absent_from_the_document(tmp_path):
    class Invented(_Fields):
        def extract_fields(self,text):
            proposal = super().extract_fields(text)
            candidate = proposal.candidates[0].model_copy(update={"raw_value":"INVENTED"})
            return proposal.model_copy(update={"candidates":(candidate,)})
    service = _svc_with(tmp_path,text_extractor=_Text(),field_extractor=Invented())
    actor = service.registry.actors["DEMO-COMPANY-BAT"]
    with pytest.raises(BousslaError) as exc:
        service.upload_document(actor,CASE,PDF,"invoice.pdf","application/pdf",1,"invented")
    assert exc.value.code is ErrorCode.INVALID_EVIDENCE_REFERENCE
    assert service.store.case_meta(CASE)["version"] == 1

def test_internal_notifications_are_durable_and_role_scoped(svc, actors):
    company, officer, other = actors
    response = to_proposal(svc, actors)
    svc.accept_evidence(officer, CASE, response.proposal_ids[0], ver(svc), "notify-accept")
    agent_feed = svc.get_notifications(officer, CASE)
    company_feed = svc.get_notifications(company, CASE)
    agent_kinds = {item["kind"] for item in agent_feed["items"]}
    company_kinds = {item["kind"] for item in company_feed["items"]}
    assert {"UPLOAD", "DOCUMENT_ANALYZED", "RESPONSE", "SCORE_CHANGED"} <= agent_kinds
    assert "REQUEST_PUBLISHED" in company_kinds
    assert "DOCUMENT_ANALYZED" in company_kinds
    assert not {"SCORE_CHANGED", "RESPONSE", "EVIDENCE_ACCEPTED"} & company_kinds
    assert all(item["status"] == "RECORDED" for item in company_feed["items"])
    assert svc.get_notifications(officer, CASE) == agent_feed
    assert code(lambda: svc.get_notifications(other, CASE)) is ErrorCode.CROSS_COMPANY

def test_resolution_impact_is_officer_only_and_read_only(svc, actors):
    company, officer, _ = actors
    before = ver(svc)
    view = svc.get_case(officer, CASE)
    assert view.impact_if_resolved
    assert view.impact_if_resolved[0].before_index == view.score.review_index == 40
    assert view.impact_if_resolved[0].after_index == 0
    assert all(step.hypothetical for step in view.impact_if_resolved)
    assert "impact_if_resolved" not in svc.get_case(company, CASE).model_dump()
    assert ver(svc) == before

def test_network_has_source_backed_nodes_and_scoped_views(svc, actors):
    company, officer, other = actors
    graph = svc.get_network(officer)
    kinds = {node.kind for node in graph.nodes}
    assert {"COMPANY", "INVOICE", "PAYMENT", "DOCUMENT", "PROJECT", "CASE", "TRANSACTION"} <= kinds
    assert all(edge.source_ids and edge.source in {node.node_id for node in graph.nodes}
               and edge.target in {node.node_id for node in graph.nodes} for edge in graph.edges)
    assert {"SELLS_TO", "BUYS_FROM", "ISSUED", "RECEIVED", "PAID", "JUSTIFIED_BY", "BELONGS_TO_PROJECT"} <= {edge.kind for edge in graph.edges}
    assert "local_path" not in graph.model_dump_json()
    assert svc.get_network(officer, case_id=CASE).scope == "CASE"
    assert svc.get_network(officer, company_id="DEMO-BAT").scope == "COMPANY"
    assert code(lambda: svc.get_network(company)) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.get_network(other)) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.get_network(officer, case_id="CASE-NOT-ASSIGNED")) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.get_network(officer, company_id="UNKNOWN-COMPANY")) is ErrorCode.NOT_FOUND


def test_network_does_not_infer_payment_link_without_allocation(svc, actors):
    from boussla.network import build_network
    facts = svc._facts(CASE, ver(svc))
    facts["payment_allocation"] = []
    graph = build_network(((CASE, facts),), names={})
    assert any(node.kind == "PAYMENT" for node in graph.nodes)
    assert not any(edge.kind == "PAID" for edge in graph.edges)

def test_investigation_answer_is_cited_officer_only_and_read_only(svc, actors):
    company, officer, other = actors
    before = ver(svc)
    answer = svc.ask_investigation(officer, CASE, "Pourquoi ce dossier est prioritaire ?")
    assert answer.mode == "TEMPLATE" and answer.authoritative is False
    assert "Urgence de traitement" in answer.answer_fr and "+40" in answer.answer_fr
    assert answer.citations and all(item.source_id for item in answer.citations)
    assert answer.case_version == before and ver(svc) == before
    assert code(lambda: svc.ask_investigation(company, CASE, "Pourquoi ?")) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.ask_investigation(other, CASE, "Pourquoi ?")) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.ask_investigation(officer, CASE, "x")) is ErrorCode.INVALID_INPUT

def test_investigation_retrieves_network_and_decision_sources(svc, actors):
    company, officer, _ = actors
    network = svc.ask_investigation(officer, CASE, "Quelles relations réseau ?")
    assert "Relation enregistrée" in network.answer_fr
    assert any(citation.kind == "TRANSACTION" for citation in network.citations)
    documents = svc.ask_investigation(officer, CASE, "Quels documents manquent ?")
    assert documents.citations and all(citation.source_id for citation in documents.citations)
    response = to_proposal(svc, actors)
    svc.accept_evidence(officer, CASE, response.proposal_ids[0], ver(svc), "investigate-decision")
    decision = svc.ask_investigation(officer, CASE, "Quelle décision a été validée ?")
    assert "Acceptée" in decision.answer_fr
    assert any(citation.kind == "EVENT" for citation in decision.citations)
    assert svc.ask_investigation(officer, CASE, "Question sans catégorie reconnue").citations


def test_investigation_reads_scoped_document_report_without_authenticity_verdict(svc, actors):
    company, officer, _ = actors
    upload = svc.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf", ver(svc), "report-upload")
    doc_id = upload.document.document_id
    before = ver(svc)
    answer = svc.ask_investigation(officer, CASE, f"Analyse du document {doc_id} ?")
    assert doc_id in answer.answer_fr
    assert "Authenticité à vérifier" in answer.answer_fr
    assert any(c.source_id == doc_id and c.kind == "DOCUMENT" for c in answer.citations)
    assert "faux document" not in answer.answer_fr.lower()
    assert answer.case_version == before and ver(svc) == before
    assert code(lambda: svc.ask_investigation(company, CASE, f"Analyse du document {doc_id} ?")) is ErrorCode.FORBIDDEN


def test_case_review_decision_is_internal_versioned_and_requires_resolved_causes(svc, actors):
    company, officer, _ = actors
    initial = ver(svc)
    assert code(lambda: svc.record_case_decision(company, CASE, "ESCALATE", "Examen renforcé requis", initial, "company")) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.record_case_decision(officer, CASE, "RESOLVE", "Revue terminée sans réserve", initial, "premature")) is ErrorCode.INVALID_STATE
    assert ver(svc) == initial
    escalated = svc.record_case_decision(officer, CASE, "ESCALATE", "Examen renforcé requis", initial, "escalate")
    assert escalated.review_index == 40 and ver(svc) == initial + 1
    assert svc.record_case_decision(officer, CASE, "ESCALATE", "Examen renforcé requis", initial, "escalate") == escalated
    assert svc.get_case(officer, CASE).case_decisions == (escalated,)
    assert "case_decisions" not in svc.get_case(company, CASE).model_dump()
    assert not any(event.kind.startswith("CASE_REVIEW_") for event in svc.get_history(company, CASE).events)
    assert any(item["kind"] == "CASE_REVIEW_ESCALATE" for item in svc.get_notifications(officer, CASE)["items"])
    assert "Examen renforcé requis" in svc.ask_investigation(officer, CASE, "Quelle décision récente ?").answer_fr
    audit = svc.get_audit(officer, CASE)["records"][-1]
    assert audit["action"] == "CASE_REVIEW_ESCALATE" and audit["actor_id"] == officer.actor_id
    assert audit["fact_changes"][0]["after"]["kind"] == "ESCALATE"
    response = to_proposal(svc, actors)
    svc.accept_evidence(officer, CASE, response.proposal_ids[0], ver(svc), "accept-after-escalate")
    resolved = svc.record_case_decision(officer, CASE, "RESOLVE", "Toutes les causes sont résolues", ver(svc), "resolve")
    assert resolved.review_index == 0 and resolved.source_cause_ids == ()
    assert svc.get_case(officer, CASE).score.review_index == 0


def test_investigation_retrieves_native_pdf_passage_with_page_and_no_write(svc, actors):
    from boussla.contracts import DocumentText
    from boussla.documents.native_text import NativePdfExtractor
    company, officer, _ = actors
    svc.text_extractor = NativePdfExtractor()
    upload = svc.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf", ver(svc), "passage-upload")
    document_id = upload.document.document_id
    text = svc.store.fact(CASE, "document_text", document_id, DocumentText)
    assert text is not None and text.status in ("OK", "PARTIAL")
    version_before = ver(svc)
    answer = svc.ask_investigation(officer, CASE, "Que dit le document sur TX-001 ?")
    assert "Extrait natif non vérifié" in answer.answer_fr
    assert any(c.kind == "DOCUMENT_PAGE" and c.source_id == f"{document_id}:p1" for c in answer.citations)
    assert answer.case_version == version_before and ver(svc) == version_before
    audit_text = next(c for record in svc.get_audit(officer, CASE)["records"]
                      for c in record["fact_changes"] if c["kind"] == "document_text")
    assert "pages" not in audit_text["after"] and audit_text["after"]["text_sha256"]


def test_officer_notifications_distinguish_current_signals_from_recorded_events(svc, actors, monkeypatch):
    from datetime import datetime, timezone
    from boussla.contracts import BehaviorSignal, DocumentAnalysisReport, DocumentCheck
    company, officer, _ = actors
    original = svc.get_case
    view = original(officer, CASE)
    signal = BehaviorSignal(code="RESPONSE_DELAY_DEVIATION", metric_code="RESPONSE_DELAY",
        observed_value="13", baseline_value="2.8", ratio="4.64", data_quality="LIMITED_DATA",
        baseline_months=6, current_sample_size=1, source_ids=("REQ-1",),
        explanation_fr="Délai observé 13 jours contre 2,8 jours habituels ; données limitées.")
    profile = view.behavior_profile.model_copy(update={"signals": (signal,)})
    document = view.documents[0]
    report = DocumentAnalysisReport(document_id=document.document.document_id, case_version=view.case_version,
        calculated_at=datetime.now(timezone.utc), rule_version="test", classification="INVOICE",
        checks=(DocumentCheck(code="METADATA_CHRONOLOGY", status="WARN",
                              explanation_fr="Date à vérifier", source_ids=(document.document.document_id,)),),
        stages=(), proposed_action="REVIEW_DOCUMENT")
    fake = view.model_copy(update={"behavior_profile": profile,
        "documents": (document.model_copy(update={"analysis": report}), *view.documents[1:]),
        "triage": view.triage.model_copy(update={"triage_priority": 82})})
    monkeypatch.setattr(svc, "get_case", lambda actor, case_id: fake if actor.role is Role.OFFICER else original(actor, case_id))
    agent = svc.get_notifications(officer, CASE)
    current = {item["kind"]: item for item in agent["items"] if item["status"] == "CURRENT_SIGNAL"}
    assert set(current) == {"HISTORY_DEVIATION", "DOCUMENT_REVIEW_SIGNAL", "CASE_URGENT"}
    assert current["HISTORY_DEVIATION"]["source_ids"] == ["REQ-1"]
    assert current["DOCUMENT_REVIEW_SIGNAL"]["source_event_id"] is None
    assert all(item["status"] == "RECORDED" for item in svc.get_notifications(company, CASE)["items"])


def test_completed_recommendations_come_only_from_recorded_response_and_decision(svc, actors):
    company, officer, _ = actors
    assert not any(action.status == "COMPLETED" for action in svc.get_case(officer, CASE).recommended_actions)
    response = to_proposal(svc, actors)
    awaiting = svc.get_case(officer, CASE).recommended_actions
    assert any(action.status == "COMPLETED" and action.kind == "WAIT_RESPONSE" for action in awaiting)
    svc.accept_evidence(officer, CASE, response.proposal_ids[0], ver(svc), "complete-action")
    after = svc.get_case(officer, CASE).recommended_actions
    assert any(action.status == "COMPLETED" and action.kind == "VALIDATE_CAUSE"
               and response.proposal_ids[0] in action.source_ids for action in after)
    assert any(action.status == "COMPLETED" and action.kind == "REVIEW_DOCUMENT" for action in after)
    assert all(action.rule_version == "recommended-actions-2" for action in after)
    assert "recommended_actions" not in svc.get_case(company, CASE).model_dump()


def test_notification_read_receipts_are_actor_scoped_idempotent_and_version_neutral(svc, actors):
    from starlette.testclient import TestClient
    from boussla.web.app import create_app

    company, officer, other = actors
    to_proposal(svc, actors)
    company_item = next(item for item in svc.get_notifications(company, CASE)["items"]
                        if item["kind"] == "REQUEST_PUBLISHED")
    officer_item = next(item for item in svc.get_notifications(officer, CASE)["items"]
                        if item["kind"] == "RESPONSE")
    before = ver(svc)
    first = svc.mark_notification_read(company, CASE, company_item["notification_id"])
    assert svc.mark_notification_read(company, CASE, company_item["notification_id"]) == first
    assert ver(svc) == before
    assert next(item for item in svc.get_notifications(company, CASE)["items"]
                if item["notification_id"] == company_item["notification_id"])["read_at"] == first["read_at"]
    assert next(item for item in svc.get_notifications(officer, CASE)["items"]
                if item["notification_id"] == officer_item["notification_id"])["read_at"] is None
    assert code(lambda: svc.mark_notification_read(other, CASE, company_item["notification_id"])) is ErrorCode.CROSS_COMPANY
    assert code(lambda: svc.mark_notification_read(company, CASE, officer_item["notification_id"])) is ErrorCode.INVALID_INPUT
    assert code(lambda: svc.mark_notification_read(officer, CASE, "CURRENT-URGENT-CASE-BRICKS-001")) is ErrorCode.INVALID_INPUT
    assert svc.store.notification_reads(CASE, company.actor_id)[company_item["notification_id"]] == first["read_at"]
    with TestClient(create_app(svc)) as client:
        url = f"/api/cases/{CASE}/notifications/{officer_item['notification_id']}/read"
        assert client.post(url, headers={"X-Boussla-Demo-Role": "OFFICER"}).status_code == 200
        assert client.post(url, headers={"X-Boussla-Demo-Role": "COMPANY"}).status_code == 400


def test_pending_request_reminders_are_current_scoped_and_disappear_after_response(svc, actors, monkeypatch):
    from datetime import timedelta
    company, officer, _ = actors
    draft = svc.prepare_clarification(officer, CASE, ver(svc))
    request = svc.publish_clarification(officer, CASE, draft.draft_id, ver(svc), "reminder-publish")
    target = request.request.target_response_at
    version_before_reads = ver(svc)
    assert target is not None
    monkeypatch.setattr(svc, "clock", lambda: target - timedelta(days=1))
    near = svc.get_notifications(company, CASE)["items"]
    reminder = next(item for item in near if item["kind"] == "REQUEST_TARGET_APPROACHING")
    assert reminder["status"] == "CURRENT_SIGNAL"
    assert reminder["source_ids"] == [request.request.request_id]
    assert reminder["read_at"] is None
    assert code(lambda: svc.mark_notification_read(company, CASE, reminder["notification_id"])) is ErrorCode.INVALID_INPUT
    monkeypatch.setattr(svc, "clock", lambda: target + timedelta(days=1))
    assert any(item["kind"] == "REQUEST_FOLLOW_UP" for item in svc.get_notifications(company, CASE)["items"])
    assert any(item["kind"] == "REQUEST_FOLLOW_UP_OFFICER" for item in svc.get_notifications(officer, CASE)["items"])
    assert ver(svc) == version_before_reads
    svc.submit_response(company, CASE, request.request.request_id,
                        {"answers": {"Q-PROJECT-ALLOCATION": "À vérifier"}, "document_ids": []},
                        ver(svc), "reminder-response")
    assert not any(item["kind"].startswith("REQUEST_FOLLOW_UP")
                   for item in svc.get_notifications(company, CASE)["items"])


def test_company_receives_neutral_scoped_document_decision_notice(svc, actors):
    company, officer, other = actors
    response = to_proposal(svc, actors)
    proposal_id = response.proposal_ids[0]
    svc.reject_evidence(officer, CASE, proposal_id, ver(svc), "Pièce insuffisante", "company-notice")
    company_items = svc.get_notifications(company, CASE)["items"]
    notice = next(item for item in company_items if item["kind"] == "DOCUMENT_DECISION_RECORDED")
    assert notice["status"] == "RECORDED" and proposal_id in notice["source_ids"]
    decision_event = next(event for event in svc.store.events(CASE)
                          if event.kind == "EVIDENCE_REJECTED" and proposal_id in event.fact_ids)
    assert notice["case_version"] == decision_event.case_version
    assert "retenue" in notice["message_fr"]
    assert "Pièce insuffisante" not in notice["message_fr"]
    assert all(item["kind"] != "EVIDENCE_REJECTED" for item in company_items)
    assert code(lambda: svc.get_notifications(other, CASE)) is ErrorCode.CROSS_COMPANY
    assert svc.mark_notification_read(company, CASE, notice["notification_id"])["read_at"]
