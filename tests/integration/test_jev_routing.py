"""Jev document routing wired into upload: candidate class only, explicit MANUAL
fallback, and no influence on checks or the review index. Offline (MockTransport)."""
import httpx
import pytest

from boussla.adapters.jev import CRITERIA, JevDocumentRouter
from boussla.config import FIXTURE_ROOT, get_settings
from boussla.contracts import DocumentClass, Mode
from boussla.documents.native_text import NativePdfExtractor
from boussla.services import BousslaAppService, build_service

CASE = "CASE-BRICKS-001"
ALLOC_PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


def jev_reply(choice: str, confidence: float = 0.99):
    probs = {k: (confidence if k == choice else (1 - confidence) / (len(CRITERIA) - 1)) for k in CRITERIA}
    body = {"model": "jev-1.13.0", "answers": {"document_type": {
        "type": "choice", "choice": choice, "confidence": confidence, "probabilities": probs}}}
    return lambda request: httpx.Response(200, json=body)


def service_with(handler) -> BousslaAppService:
    base = build_service()
    router = JevDocumentRouter(api_key="test-key-not-real", client=httpx.Client(transport=httpx.MockTransport(handler)))
    return BousslaAppService(base.store, base.registry, settings=base.settings,
                             text_extractor=NativePdfExtractor(), document_router=router)


def upload(svc):
    co = svc.registry.actors["DEMO-COMPANY-BAT"]
    return svc.upload_document(co, CASE, ALLOC_PDF, "affectation.pdf", "application/pdf",
                               svc.store.case_meta(CASE)["version"], "u")


def officer_view(svc):
    return svc.get_case(svc.registry.actors["DEMO-OFFICER"], CASE)


def test_live_routing_is_stored_and_reported():
    svc = service_with(jev_reply("ALLOCATION_RESPONSE"))
    dv = upload(svc)
    assert dv.routing.mode is Mode.LIVE and dv.routing.candidate_class is DocumentClass.ALLOCATION_RESPONSE
    assert dv.routing.model_id == "jev-1.13.0"
    view = officer_view(svc)
    assert view.mode_by_node["router"] is Mode.LIVE
    stored = next(d for d in view.documents if d.document.document_id == dv.document.document_id)
    assert stored.routing == dv.routing


@pytest.mark.parametrize("handler", [
    lambda request: httpx.Response(503),
    lambda request: httpx.Response(401),
    lambda request: (_ for _ in ()).throw(httpx.ReadTimeout("timeout", request=request)),
    jev_reply("INVOICE", confidence=0.40),  # below the adapter's confidence floor
    lambda request: httpx.Response(200, json={"unexpected": True}),
])
def test_unavailable_or_unsure_provider_falls_back_to_manual(handler):
    svc = service_with(handler)
    dv = upload(svc)
    assert dv.routing.mode is Mode.MANUAL and dv.routing.candidate_class is DocumentClass.OTHER_OR_UNKNOWN
    assert officer_view(svc).mode_by_node["router"] is Mode.MANUAL


def test_router_exception_is_contained():
    class Broken:
        def classify(self, *args):
            raise RuntimeError("boom")
    base = build_service()
    svc = BousslaAppService(base.store, base.registry, settings=base.settings,
                            text_extractor=NativePdfExtractor(), document_router=Broken())
    assert upload(svc).routing.mode is Mode.MANUAL


def test_routing_never_changes_checks_or_index(tmp_path, monkeypatch):
    """Same upload into two separate stores, one routed with a deliberately wrong
    class: findings, severities and index must be identical."""
    routed = service_with(jev_reply("CREDIT_NOTE"))
    assert upload(routed).routing.candidate_class is DocumentClass.CREDIT_NOTE
    monkeypatch.setenv("CASE_DB_PATH", str(tmp_path / "plain.sqlite"))
    get_settings.cache_clear()
    plain = build_service()
    assert plain.store.db_path != routed.store.db_path and plain.document_router is None
    assert upload(plain).routing is None
    a, b = officer_view(routed), officer_view(plain)
    assert a.score.review_index == b.score.review_index == 40
    assert [(f.family, f.status, f.severity, f.reason_code) for f in a.findings] ==         [(f.family, f.status, f.severity, f.reason_code) for f in b.findings]
    assert a.score.contributions == b.score.contributions


def test_build_service_wires_jev_only_when_enabled_with_key(monkeypatch):
    assert build_service().document_router is None  # hermetic env: no key
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-not-real")
    monkeypatch.setenv("JEV_ENABLED", "true")
    get_settings.cache_clear()
    svc = build_service()
    assert isinstance(svc.document_router, JevDocumentRouter) and svc.document_router.model == "jev-1.13.0"
    assert "test-key-not-real" not in repr(svc.settings) and svc.settings.describe()["typesafe_key"] == "set"
    monkeypatch.setenv("JEV_ENABLED", "false")
    get_settings.cache_clear()
    assert build_service().document_router is None
