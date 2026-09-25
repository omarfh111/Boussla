"""End-to-end clarification loop and guard tests against the MOCK service."""
import pytest

from boussla.contracts import (
    Audience, BousslaError, BousslaService, CompanyCaseView, ErrorCode, FindingStatus, Mode, OfficerCaseView,
)
from boussla.mock_service import MockBousslaService, demo_actors

CASE = "CASE-BRICKS-001"
A = demo_actors()


@pytest.fixture
def svc():
    return MockBousslaService()


def qty(view):
    return next(f for f in view.findings if f.family.value == "QUANTITY")


def run_to_proposal(svc):
    off, co = A["officer"], A["company"]
    v = svc.get_case(off, CASE).case_version
    draft = svc.prepare_clarification(off, CASE, v)
    req = svc.publish_clarification(off, CASE, draft.draft_id, v, "pub-1")
    v = svc.get_case(co, CASE).case_version
    resp = svc.submit_response(co, CASE, req.request.request_id,
                               {"answers": {"Q-PROJECT-ALLOCATION": "1000 P1, 1000 P2"},
                                "allocation": {"P1": "1000", "P2": "1000"}}, v, "resp-1")
    return resp


def test_mock_satisfies_service_protocol(svc):
    assert isinstance(svc, BousslaService)


def test_views_are_mock_and_scoped(svc):
    c = svc.get_case(A["company"], CASE)
    o = svc.get_case(A["officer"], CASE)
    assert isinstance(c, CompanyCaseView) and isinstance(o, OfficerCaseView)
    assert c.mode is Mode.MOCK and o.mode is Mode.MOCK and "MOCK" in c.banner_fr
    assert qty(o).status is FindingStatus.UNRESOLVED and o.score.review_index == 40


def test_wrong_company_forbidden(svc):
    with pytest.raises(BousslaError) as e:
        svc.get_case(A["other_company"], CASE)
    assert e.value.code is ErrorCode.CROSS_COMPANY


def test_company_cannot_accept_or_see_queue(svc):
    resp = run_to_proposal(svc)
    co = A["company"]
    with pytest.raises(BousslaError) as e:
        svc.accept_evidence(co, CASE, resp.proposal_ids[0], resp.case_version, "k")
    assert e.value.code is ErrorCode.FORBIDDEN
    with pytest.raises(BousslaError):
        svc.list_queue(co, None, 10)


def test_full_loop_revises_once_and_resolves(svc):
    resp = run_to_proposal(svc)
    off = A["officer"]
    r1 = svc.accept_evidence(off, CASE, resp.proposal_ids[0], resp.case_version, "acc-1")
    assert r1.outcome == "ACCEPTED" and r1.new_version == resp.case_version + 1
    after = {a.target_project_id: a.quantity for a in r1.allocations_after}
    assert after == {"P1": "1000", "P2": "1000"}
    assert r1.score_before.review_index == 40 and r1.score_after.review_index == 0
    # Identical retry returns stored outcome even though the version advanced.
    r2 = svc.accept_evidence(off, CASE, resp.proposal_ids[0], resp.case_version, "acc-1")
    assert r2.replayed and r2.new_version == r1.new_version
    assert svc.get_case(off, CASE).case_version == r1.new_version


def test_same_key_different_payload_conflicts(svc):
    resp = run_to_proposal(svc)
    off = A["officer"]
    svc.accept_evidence(off, CASE, resp.proposal_ids[0], resp.case_version, "acc-1")
    with pytest.raises(BousslaError) as e:
        svc.reject_evidence(off, CASE, resp.proposal_ids[0], resp.case_version, "x", "acc-1")
    # different action namespace -> treated as new action, which is stale now
    assert e.value.code is ErrorCode.STALE_REVISION
    with pytest.raises(BousslaError) as e:
        svc.accept_evidence(off, CASE, resp.proposal_ids[0], resp.case_version + 1, "acc-1")
    assert e.value.code is ErrorCode.IDEMPOTENCY_CONFLICT


def test_stale_new_action_rejected(svc):
    resp = run_to_proposal(svc)
    with pytest.raises(BousslaError) as e:
        svc.accept_evidence(A["officer"], CASE, resp.proposal_ids[0], resp.case_version - 1, "acc-new")
    assert e.value.code is ErrorCode.STALE_REVISION


def test_duplicate_acceptance_with_new_key_rejected(svc):
    resp = run_to_proposal(svc)
    r1 = svc.accept_evidence(A["officer"], CASE, resp.proposal_ids[0], resp.case_version, "acc-1")
    with pytest.raises(BousslaError) as e:
        svc.accept_evidence(A["officer"], CASE, resp.proposal_ids[0], r1.new_version, "acc-2")
    assert e.value.code is ErrorCode.DUPLICATE_ACCEPTANCE


def test_overflow_rejected(svc):
    off, co = A["officer"], A["company"]
    v = svc.get_case(off, CASE).case_version
    d = svc.prepare_clarification(off, CASE, v)
    req = svc.publish_clarification(off, CASE, d.draft_id, v, "p")
    resp = svc.submit_response(co, CASE, req.request.request_id, {"allocation": {"P1": "1500", "P2": "1000"}},
                               v + 1, "r")
    with pytest.raises(BousslaError) as e:
        svc.accept_evidence(off, CASE, resp.proposal_ids[0], resp.case_version, "a")
    assert e.value.code is ErrorCode.ALLOCATION_OVERFLOW


def test_draft_invalidated_by_record_change(svc):
    off, co = A["officer"], A["company"]
    v = svc.get_case(off, CASE).case_version
    draft = svc.prepare_clarification(off, CASE, v)
    svc.submit_context(co, CASE, {"purpose_text": "maj", "purpose_category": "CONSTRUCTION_PROJECT"}, v, "ctx")
    with pytest.raises(BousslaError) as e:
        svc.publish_clarification(off, CASE, draft.draft_id, v + 1, "pub")
    assert e.value.code is ErrorCode.STALE_REVISION


def test_company_analysis_hides_findings(svc):
    v = svc.get_case(A["company"], CASE).case_version
    an = svc.start_analysis(A["company"], CASE, v)
    assert an.audience is Audience.COMPANY and not an.findings and an.score is None and an.questions


def test_upload_limits(svc):
    v = svc.get_case(A["company"], CASE).case_version
    with pytest.raises(BousslaError) as e:
        svc.upload_document(A["company"], CASE, b"x", "a.exe", "application/octet-stream", v, "u")
    assert e.value.code is ErrorCode.UNSUPPORTED_FILE
    dv = svc.upload_document(A["company"], CASE, b"%PDF-1.4", "alloc.pdf", "application/pdf", v, "u2")
    assert dv.document.acquisition_channel.value == "COMPANY_UPLOAD"
    assert dv.document.origin_group_id == "COMPANY-DEMO-BAT"


def test_history_and_export(svc):
    run_to_proposal(svc)
    h = svc.get_history(A["officer"], CASE)
    assert len(h.revisions) >= 3 and h.events
    v = svc.get_case(A["officer"], CASE).case_version
    art = svc.export_dossier(A["officer"], CASE, Audience.COMPANY, v)
    assert "MOCK" in art.filename and "QUANTITY" not in art.content_markdown
