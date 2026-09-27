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
    assert "aucun envoi externe" in req.text_fr and "pas un délai légal" in req.text_fr


def test_company_analysis_questions_without_internal_data(svc, actors):
    an = svc.start_analysis(actors[0], CASE, ver(svc))
    assert an.status is AnalysisStatus.AWAITING_COMPANY_ANSWER and an.questions
    assert an.findings == () and an.score is None
    after = svc.answer_questions(actors[0], CASE, an.analysis_id, {an.questions[0].question_id: "réponse"}, ver(svc), "ans")
    assert an.questions[0].question_id not in {q.question_id for q in after.questions}


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
