"""Progress evidence must be linked to the cause it provisionally reduces."""

from datetime import datetime, timezone

import pytest

from boussla.config import FIXTURE_ROOT, Settings
from boussla.contracts import (BousslaError, CandidateField, ErrorCode, EvidenceRef, ExtractionProposal,
                               FindingFamily, Mode, ProgressStage)
from boussla.review_evidence import derive_progress_evidence
from boussla.review_progress import calculate_progress, transaction_progress_index
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import BousslaAppService
from boussla.store import CaseStore


CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


@pytest.fixture
def service(tmp_path):
    settings = Settings(case_db_path=tmp_path / "case.sqlite", upload_dir=tmp_path / "uploads")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    return BousslaAppService(store, ActorRegistry.demo(), settings=settings)


def version(service):
    return service.store.case_meta(CASE)["version"]


def progress(service):
    facts = service._facts(CASE)
    evaluation = service._evaluate(CASE, "DEMO-BAT", version(service), facts)
    evidence = derive_progress_evidence(evaluation.findings, facts, None)
    causes = calculate_progress(evaluation.findings, evidence)
    return next(c for c in causes if c.family is FindingFamily.QUANTITY), transaction_progress_index(causes, "TX-001")


def request_and_answer(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    draft = service.prepare_clarification(officer, CASE, version(service))
    request = service.publish_clarification(officer, CASE, draft.draft_id, version(service), "publish")
    response = service.submit_response(company, CASE, request.request.request_id, {
        "answers": {"Q-PROJECT-ALLOCATION": "1000 unités P1, 1000 unités P2"},
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001",
                       "splits": {"P1": "1000", "P2": "1000"}},
    }, version(service), "answer")
    return company, response


def test_answer_then_later_document_advances_only_linked_cause(service):
    cause, score = progress(service)
    assert (cause.stage, score) == (ProgressStage.UNRESOLVED, 40)

    company, response = request_and_answer(service)
    cause, score = progress(service)
    assert (cause.stage, score) == (ProgressStage.EXPLANATION_RECEIVED, 30)
    assert cause.provisional and response.response.response_id in cause.source_ids

    document = service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                                       version(service), "upload", response_id=response.response.response_id)
    cause, score = progress(service)
    assert (cause.stage, score) == (ProgressStage.EVIDENCE_RECEIVED, 20)
    assert document.document.document_id in cause.source_ids
    stored_response = next(r for r in service._facts(CASE)["response"]
                           if r.response_id == response.response.response_id)
    assert document.document.document_id in stored_response.document_ids
    proposal = next(p for p in service._facts(CASE)["proposal"]
                    if p.source_response_id == response.response.response_id)
    assert proposal.source_document_id == document.document.document_id


def test_unknown_response_cannot_attach_document(service):
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    before = version(service)
    with pytest.raises(BousslaError) as exc:
        service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                                version(service), "upload", response_id="RESP-NOT-FOUND")
    assert exc.value.code in (ErrorCode.INVALID_EVIDENCE_REFERENCE, ErrorCode.NOT_FOUND)
    assert version(service) == before


def test_unlinked_upload_does_not_advance_answer_stage(service):
    company, _ = request_and_answer(service)
    service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                            version(service), "upload")
    cause, score = progress(service)
    assert (cause.stage, score) == (ProgressStage.EXPLANATION_RECEIVED, 30)


def test_unrelated_answer_does_not_reduce_quantity_cause(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    draft = service.prepare_clarification(officer, CASE, version(service))
    request = service.publish_clarification(officer, CASE, draft.draft_id, version(service), "publish")
    service.submit_response(company, CASE, request.request.request_id,
                            {"answers": {"Q-SUPPORTING-DOC": "Je transmettrai un autre dossier."}},
                            version(service), "unrelated")
    cause, score = progress(service)
    assert (cause.stage, score) == (ProgressStage.UNRESOLVED, 40)


def test_linked_upload_is_idempotent_and_cannot_be_attached_by_officer(service):
    _, response = request_and_answer(service)
    officer = service.registry.actors["DEMO-OFFICER"]
    before = version(service)
    with pytest.raises(BousslaError) as exc:
        service.upload_document(officer, CASE, PDF, "allocation.pdf", "application/pdf",
                                before, "officer-upload", response_id=response.response.response_id)
    assert exc.value.code is ErrorCode.INVALID_EVIDENCE_REFERENCE
    assert version(service) == before
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    first = service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                                    before, "company-upload", response_id=response.response.response_id)
    replay = service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                                     before, "company-upload", response_id=response.response.response_id)
    assert replay == first and version(service) == before + 1


def test_officer_score_and_revision_follow_progressive_stages(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    assert service.get_case(officer, CASE).score.review_index == 40
    company, response = request_and_answer(service)
    answered = service.get_case(officer, CASE).score
    assert answered.review_index == 30
    assert answered.raw_review_index == 40
    assert answered.cause_progress[0].provisional
    assert service.store.revisions(CASE)[-1].score_snapshot.review_index == 30
    assert service.list_queue(officer, datetime.now(timezone.utc), 10).items[0].review_index == 30
    service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                            version(service), "upload", response_id=response.response.response_id)
    uploaded = service.get_case(officer, CASE).score
    assert uploaded.review_index == 20
    assert uploaded.cause_progress[0].stage is ProgressStage.EVIDENCE_RECEIVED
    assert service.store.revisions(CASE)[-1].score_snapshot.review_index == 20
    assert service.list_queue(officer, datetime.now(timezone.utc), 10).items[0].review_index == 20
    officer_view = service.get_case(officer, CASE)
    assert officer_view.operational_confidence_index is None
    assert officer_view.operational_confidence_status == "INSUFFICIENT_DATA"
    assert officer_view.history_signal_index is None
    assert officer_view.history_signal_status == "INSUFFICIENT_DATA"
    company_view = service.get_case(company, CASE).model_dump()
    assert "score" not in company_view
    assert "operational_confidence_index" not in company_view
    assert "history_signal_index" not in company_view
    result = service.accept_evidence(officer, CASE, response.proposal_ids[0], version(service), "accept")
    assert result.score_before.review_index == 20
    assert result.score_after.review_index == 0
    assert result.score_after.cause_progress[0].stage is ProgressStage.RESOLVED
    assert service.store.revisions(CASE)[-1].score_snapshot.cause_progress[0].stage is ProgressStage.RESOLVED
    assert service.evaluate(CASE, version=result.previous_version).score.review_index == 20


def test_rejection_restores_raw_cause_weight(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company, response = request_and_answer(service)
    service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                            version(service), "upload", response_id=response.response.response_id)
    rejected = service.reject_evidence(officer, CASE, response.proposal_ids[0],
                                       version(service), "pièce contradictoire", "reject")
    assert rejected.score_before.review_index == 20
    assert rejected.score_after.review_index == 40
    assert rejected.score_after.cause_progress[0].stage is ProgressStage.UNRESOLVED


def test_source_backed_coherence_and_contradiction_are_reversible(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company, response = request_and_answer(service)
    doc = service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                                  version(service), "upload", response_id=response.response.response_id)
    doc_id = doc.document.document_id

    def record(p2):
        fields = {"allocation.transaction_id": "TX-001", "allocation.line_id": "LINE-BUY-001",
                  "allocation.P1.quantity": "1000", "allocation.P2.quantity": p2}
        candidates = tuple(CandidateField(field_name=name, raw_value=value, normalized_value=value,
                                          evidence_refs=(EvidenceRef(document_id=doc_id, page=1,
                                                                     exact_text=value),))
                           for name, value in fields.items())
        with service.store.write(CASE) as tx:
            tx.put("extraction", "EXTRACT-ALLOC", ExtractionProposal(
                proposal_id="EXTRACT-ALLOC", document_id=doc_id, candidates=candidates,
                mode=Mode.MANUAL, prompt_version="test-source-backed", status="CONFIRMED"))
            tx.commit_version("Champs de pièce contrôlés")

    record("1000")
    coherent = service.get_case(officer, CASE).score
    assert coherent.review_index == 10
    assert coherent.cause_progress[0].stage is ProgressStage.EVIDENCE_COHERENT
    record("900")
    contradictory = service.get_case(officer, CASE).score
    assert contradictory.review_index == 40
    assert contradictory.cause_progress[0].reason_code == "DOCUMENT_ALLOCATION_CONTRADICTION"
    record("1000")
    assert service.get_case(officer, CASE).score.review_index == 10
    accepted = service.accept_evidence(officer, CASE, response.proposal_ids[0], version(service), "accept")
    assert accepted.score_before.review_index == 10
    assert accepted.score_after.review_index == 0
