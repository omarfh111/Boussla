"""Progress evidence must be linked to the cause it provisionally reduces."""

from datetime import datetime, timedelta, timezone

import pytest

from boussla.config import FIXTURE_ROOT, Settings
from boussla.contracts import (BousslaError, CandidateField, ErrorCode, EvidenceRef, ExtractionProposal,
                               FindingFamily, Mode, ProgressStage, ClarificationRequest, RequestStatus, RequestView)
from boussla.review_evidence import derive_progress_evidence
from boussla.review_progress import calculate_progress, transaction_progress_index
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import BousslaAppService
from boussla.store import CaseStore, utcnow


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
    assert officer_view.operational_confidence_eligible_observations == 1
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
    accepted_view = service.get_case(officer, CASE)
    assert accepted_view.operational_confidence_index is None
    assert accepted_view.operational_confidence_eligible_observations == 2
    assert service.store.revisions(CASE)[-1].score_snapshot.cause_progress[0].stage is ProgressStage.RESOLVED
    assert service.evaluate(CASE, version=result.previous_version).score.review_index == 20


def test_officer_history_reconstructs_deadline_only_confidence_delta(service):
    now = utcnow()
    due = now + timedelta(hours=1)
    with service.store.write(CASE) as tx:
        tx.require_version(version(service))
        for number in range(3):
            request = ClarificationRequest(request_id=f"REQ-DEADLINE-{number}", case_id=CASE,
                                           company_id="DEMO-BAT", case_version=version(service) + 1,
                                           status=RequestStatus.PUBLISHED_IN_DEMO,
                                           published_at=now, target_response_at=due)
            tx.put("request", request.request_id,
                   RequestView(request=request, questions=(), text_fr="Justifier", mode=Mode.LIVE))
        tx.commit_version("Trois demandes de démonstration")
    officer = service.registry.actors["DEMO-OFFICER"]
    service.clock = lambda: now
    before_history = service.get_history(officer, CASE)
    assert before_history.operational_confidence_changes == ()
    service.clock = lambda: due + timedelta(hours=1)
    history = service.get_history(officer, CASE)
    change = history.operational_confidence_changes[-1]
    assert change.from_version == change.to_version == version(service)
    assert change.before_index is None and change.after_index == 0
    assert change.factor_deltas[0].after_denominator == 3
    assert set(change.factor_deltas[0].source_ids) == {f"REQ-DEADLINE-{n}" for n in range(3)}
    assert service.get_history(officer, CASE).operational_confidence_changes == history.operational_confidence_changes
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    assert "operational_confidence_changes" not in service.get_history(company, CASE).model_dump()


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


def test_empty_explanation_does_not_earn_provisional_reduction(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    draft = service.prepare_clarification(officer, CASE, version(service))
    request = service.publish_clarification(officer, CASE, draft.draft_id, version(service), "blank-publish")
    service.submit_response(company, CASE, request.request.request_id,
                            {"answers": {"Q-PROJECT-ALLOCATION": "   "}}, version(service), "blank-answer")
    assert service.get_case(officer, CASE).score.review_index == 40


def test_progress_snapshots_identify_engine_causes_and_human_resolution(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company, response = request_and_answer(service)
    service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
                            version(service), "meta-upload", response_id=response.response.response_id)
    before = service.get_case(officer, CASE).score
    result = service.accept_evidence(officer, CASE, response.proposal_ids[0], version(service), "meta-accept")
    cause = result.score_after.cause_progress[0]
    assert cause.cause_id == before.cause_progress[0].cause_id
    assert cause.initial_weight == "40" and cause.current_contribution == "0"
    assert cause.resolved_by == officer.actor_id and cause.resolved_at is not None
    assert cause.rule_version and cause.evidence_ids and cause.explanation_ids
    snapshot = service.store.revisions(CASE)[-1].score_snapshot
    assert snapshot.calculated_at == snapshot.cutoff
    assert snapshot.engine_version and snapshot.rules_version
    assert snapshot.cause_ids == tuple(c.cause_id for c in snapshot.cause_progress)
    assert service.evaluate(CASE, version=result.new_version).score == snapshot


def test_public_transcription_api_reaches_coherence_and_persists_recalculation(service):
    from starlette.testclient import TestClient
    from boussla.documents.native_text import NativePdfExtractor
    from boussla.web.app import create_app
    service.text_extractor = NativePdfExtractor()
    officer = service.registry.actors["DEMO-OFFICER"]
    company, response = request_and_answer(service)
    document = service.upload_document(company, CASE, PDF, "allocation.pdf", "application/pdf",
        version(service), "real-upload", response_id=response.response.response_id)
    assert service.get_case(officer, CASE).score.review_index == 20
    extraction = document.extraction
    assert extraction is not None and extraction.status == "PROPOSED"
    fields = {c.field_name: c.normalized_value for c in extraction.candidates}
    url = f"/api/cases/{CASE}/transcriptions/{extraction.proposal_id}/confirm"
    with TestClient(create_app(service)) as client:
        payload = {"expected_version": version(service), "fields": fields}
        headers = {"X-Boussla-Demo-Role": "COMPANY", "Idempotency-Key": "real-confirm"}
        result = client.post(url, headers=headers, json=payload)
        assert result.status_code == 200, result.text
        assert "score" not in result.json()
        assert client.post(url, headers=headers, json=payload).status_code == 200
        assert client.post(url, headers={**headers, "X-Boussla-Demo-Role": "OFFICER"},
                           json=payload).status_code == 403
    assert service.get_case(officer, CASE).score.review_index == 10
    snapshot = service.store.revisions(CASE)[-1].score_snapshot
    assert snapshot.review_index == 10 and snapshot.engine_version == "progressive-review-3"
    # A correction outside the actual source cannot keep the old corroborating span.
    service.confirm_transcription(company, CASE, extraction.proposal_id,
        {**fields, "allocation.P2.quantity": "800"}, version(service), "real-correct")
    assert service.get_case(officer, CASE).score.review_index == 20
    assert service.store.revisions(CASE)[-1].score_snapshot.review_index == 20
    correction_events = [e for e in service.store.events(CASE) if e.kind == "TRANSCRIPTION_CORRECTED"]
    assert len(correction_events) == 1 and correction_events[0].actor_id == company.actor_id
    assert "allocation.P2.quantity" in correction_events[0].summary
    service.confirm_transcription(company, CASE, extraction.proposal_id, fields,
                                   version(service), "real-restore")
    assert service.get_case(officer, CASE).score.review_index == 10
    accepted = service.accept_evidence(officer, CASE, response.proposal_ids[0], version(service), "real-accept")
    assert accepted.score_after.review_index == 0


def test_five_indicators_expose_separate_metadata_without_company_leakage(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    view = service.get_case(officer, CASE)
    assert set(view.indicators) == {"document_review", "evidence_coverage", "historical_signal",
                                     "urgency", "operational_confidence"}
    assert view.indicators["document_review"].value == str(view.score.review_index)
    assert view.indicators["evidence_coverage"].value == view.score.evidence_coverage
    assert view.indicators["urgency"].value == str(view.triage.triage_priority)
    assert view.indicators["operational_confidence"].value is None
    for indicator in view.indicators.values():
        assert indicator.rule_version and indicator.calculated_at.tzinfo
        assert indicator.explanation and indicator.sample_size >= 0
    assert "indicators" not in service.get_case(company, CASE).model_dump()
    request_and_answer(service)
    advanced = service.get_case(officer, CASE)
    assert advanced.indicators["document_review"].status == "PROVISIONAL"
    assert advanced.indicators["document_review"].value == "30"


def test_behavior_profile_is_officer_only_and_uncovered_history_stays_unknown(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    company = service.registry.actors["DEMO-COMPANY-BAT"]
    view = service.get_case(officer, CASE)
    assert view.behavior_profile is not None
    assert view.behavior_profile.as_of.tzinfo
    assert all(m.status != "AVAILABLE" for m in view.behavior_profile.metrics)
    assert "behavior_profile" not in service.get_case(company, CASE).model_dump()


def test_upload_analysis_is_persisted_idempotently_and_internal_causes_are_officer_only(service):
    from boussla.documents.native_text import NativePdfExtractor
    service.text_extractor = NativePdfExtractor()
    company, response = request_and_answer(service)
    before = version(service)
    first = service.upload_document(company,CASE,PDF,"allocation.pdf","application/pdf",before,"analysis-upload",
                                    response_id=response.response.response_id)
    retry = service.upload_document(company,CASE,PDF,"allocation.pdf","application/pdf",before,"analysis-upload",
                                    response_id=response.response.response_id)
    assert first == retry and first.analysis is None
    officer = service.registry.actors["DEMO-OFFICER"]
    view = service.get_case(officer,CASE)
    doc = next(d for d in view.documents if d.document.document_id == first.document.document_id)
    assert doc.analysis and doc.analysis.rule_version == "document-pipeline-1"
    assert doc.analysis.case_version == before+1
    assert doc.analysis.linked_cause_ids == (f"{CASE}:TX-001:QUANTITY",)
    assert all(d.analysis is None for d in service.get_case(company,CASE).documents)
    assert len([e for e in service.store.events(CASE) if e.kind == "DOCUMENT_ANALYZED"]) == 1
    assert view.score.review_index == 20


def test_identical_pending_request_is_reused_without_duplicate_event(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    draft = service.prepare_clarification(officer,CASE,version(service))
    first = service.publish_clarification(officer,CASE,draft.draft_id,version(service),"first")
    draft = service.prepare_clarification(officer,CASE,version(service))
    before = version(service)
    repeated = service.publish_clarification(officer,CASE,draft.draft_id,before,"repeat")
    assert repeated.request.request_id == first.request.request_id and version(service) == before
    assert service.publish_clarification(officer,CASE,draft.draft_id,before,"repeat") == repeated
    assert len([e for e in service.store.events(CASE) if e.kind == "REQUEST_PUBLISHED"]) == 1


def test_recommended_actions_follow_progress_without_mutating_the_case(service):
    officer = service.registry.actors["DEMO-OFFICER"]
    start = service.get_case(officer,CASE)
    assert any(a.kind == "REQUEST_EXPLANATION" and a.source_causes == (f"{CASE}:TX-001:QUANTITY",)
               for a in start.recommended_actions)
    initial_version = version(service)
    company,response = request_and_answer(service)
    assert any(a.kind == "REVIEW_EVIDENCE" for a in service.get_case(officer,CASE).recommended_actions)
    assert version(service) > initial_version
    service.upload_document(company,CASE,PDF,"allocation.pdf","application/pdf",version(service),"action-doc",
                            response_id=response.response.response_id)
    actions = service.get_case(officer,CASE).recommended_actions
    assert actions and actions[0].priority == 1 and actions[0].status == "OPEN"
    assert all(a.rule_version == "recommended-actions-1" for a in actions)
    assert "recommended_actions" not in service.get_case(company,CASE).model_dump()
    before_read = version(service)
    assert service.get_case(officer,CASE).recommended_actions == actions
    assert version(service) == before_read
