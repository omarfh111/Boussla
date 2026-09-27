"""Progress evidence must be linked to the cause it provisionally reduces."""

import pytest

from boussla.config import FIXTURE_ROOT, Settings
from boussla.contracts import BousslaError, ErrorCode, FindingFamily, ProgressStage
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
