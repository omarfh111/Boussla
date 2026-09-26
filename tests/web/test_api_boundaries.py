"""HTTP boundary and abuse cases for the Starlette adapter (real service, offline)."""
import pytest
from starlette.testclient import TestClient

from boussla.config import FIXTURE_ROOT, Settings
from boussla.security import ActorRegistry
from boussla.seed import seed_demo_case
from boussla.services import BousslaAppService
from boussla.store import CaseStore
from boussla.web.app import create_app

CASE = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


@pytest.fixture
def svc(tmp_path):
    from boussla.context.assistant import ContextConsistencyAssistant
    from boussla.context.interpreter import OpenAIContextInterpreter
    settings = Settings(case_db_path=tmp_path / "case.sqlite", upload_dir=tmp_path / "up")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    return BousslaAppService(store, ActorRegistry.demo(), settings=settings,
                             context_assistant=ContextConsistencyAssistant(OpenAIContextInterpreter(api_key=None)))


@pytest.fixture
def client(svc):
    with TestClient(create_app(svc), raise_server_exceptions=False) as c:
        yield c


def h(role="COMPANY", key="k-1", **extra):
    out = {"X-Boussla-Demo-Role": role, **extra}
    if key:
        out["Idempotency-Key"] = key
    return out


def version(client, role="COMPANY"):
    return client.get(f"/api/cases/{CASE}", headers=h(role, None)).json()["case_version"]


def err(r):
    assert r.headers["content-type"].startswith("application/json"), r.text[:200]
    return r.status_code, r.json()["error"]["code"]


CTX = f"/api/cases/{CASE}/context"


@pytest.mark.parametrize("raw,expected", [
    (b"{not json", (400, "BAD_REQUEST")),
    (b"[1, 2]", (400, "BAD_REQUEST")),
    (b'"string"', (400, "BAD_REQUEST")),
])
def test_malformed_json_bodies(client, raw, expected):
    r = client.post(CTX, headers=h(**{"Content-Type": "application/json"}), content=raw)
    assert err(r) == expected


def test_oversized_json_is_rejected_even_without_honest_length(client):
    big = b'{"expected_version": 1, "context": {"purpose_text": "' + b"x" * (1024 * 1024 + 10) + b'"}}'
    assert err(client.post(CTX, headers=h(**{"Content-Type": "application/json"}), content=big)) == (413, "LIMIT_EXCEEDED")

    def chunks():  # chunked transfer: no Content-Length header at all
        yield big
    r = client.post(CTX, headers=h(**{"Content-Type": "application/json"}), content=chunks())
    assert err(r) == (413, "LIMIT_EXCEEDED")


@pytest.mark.parametrize("key", [None, "", "a" * 101, "bad key!", "bad/key"])
def test_missing_or_bad_idempotency_key(client, key):
    headers = h(key=None) if key is None else {**h(key=None), "Idempotency-Key": key}
    assert err(client.post(CTX, headers=headers, json={"expected_version": 1, "context": {}})) == (400, "BAD_REQUEST")


@pytest.mark.parametrize("value", ["missing", True, False, -1, 0, "1", 1.0, None])
def test_bad_expected_version(client, value):
    body = {"context": {}} if value == "missing" else {"expected_version": value, "context": {}}
    assert err(client.post(CTX, headers=h(), json=body)) == (400, "BAD_REQUEST")


@pytest.mark.parametrize("payload", [
    {"expected_version": 1, "context": {"purpose_text": "x", "company_id": "DEMO-OTHER"}},
    {"expected_version": 1, "context": {"nested": [{"deep": {"actor_id": "DEMO-OFFICER"}}]}},
    {"expected_version": 1, "context": {"assigned_case_ids": ["CASE-BRICKS-001"]}},
    {"expected_version": 1, "context": {"reference_expected": True}},
    {"expected_version": 1, "role": "OFFICER", "context": {}},
])
def test_identity_and_trust_fields_rejected_anywhere(client, payload):
    v = version(client)
    assert err(client.post(CTX, headers=h(), json=payload)) == (403, "FORBIDDEN")
    assert version(client) == v


def test_declared_horizon_passes_through_and_is_validated(client):
    v = version(client)
    ok = client.post(CTX, headers=h(key="ctx-ok"), json={"expected_version": v, "context": {
        "project_id": "P1", "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "Dépôt",
        "beneficiary_type": "Maître d'ouvrage", "declared_horizon": "LONGER_HORIZON",
        "planned_start": "2027-01-01", "planned_end": "2028-06-30", "stage": "Gros œuvre"}})
    assert ok.status_code == 200, ok.text
    ctx = ok.json()["context_assessment"]
    assert ctx["declared_horizon"] == "LONGER_HORIZON" and ctx["duration_days"] == 546
    assert "findings" not in ok.json() and "score" not in ok.json()
    bad = client.post(CTX, headers=h(key="ctx-bad"), json={"expected_version": v + 1, "context": {
        "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "x", "declared_horizon": "Horizon long"}})
    assert err(bad) == (400, "INSUFFICIENT_INFORMATION")


UP = f"/api/cases/{CASE}/documents"


@pytest.mark.parametrize("name,content,ctype,code", [
    ("a.pdf", PDF, "text/plain", "UNSUPPORTED_FILE"),
    ("a.pdf", b"MZ not a pdf", "application/pdf", "UNSUPPORTED_FILE"),
    ("a.pdf", PDF[:200], "application/pdf", "UNSUPPORTED_FILE"),
    ("a.pdf", b"%PDF-1.7\nbroken", "application/pdf", "UNSUPPORTED_FILE"),
    ("a.exe", PDF, "application/pdf", "UNSUPPORTED_FILE"),
], ids=["wrong-content-type", "fake-pdf-extension", "truncated-pdf", "corrupt-pdf", "exe-extension"])
def test_upload_rejections(client, name, content, ctype, code):
    v = version(client)
    r = client.post(UP, headers=h(key=f"u-{abs(hash((name, ctype, len(content))))}"), data={"expected_version": str(v)},
                    files={"file": (name, content, ctype)})
    assert err(r) == (400, code) and version(client) == v


def test_upload_size_and_form_errors(client):
    v = version(client)
    big = b"%PDF-1.4" + b"0" * (10 * 1024 * 1024 + 10)
    assert err(client.post(UP, headers=h(key="big"), data={"expected_version": str(v)},
                           files={"file": ("big.pdf", big, "application/pdf")})) == (400, "LIMIT_EXCEEDED")
    assert err(client.post(UP, headers=h(key="nofile"), data={"expected_version": str(v)})) == (400, "BAD_REQUEST")
    assert err(client.post(UP, headers=h(key="badv"), data={"expected_version": "x"},
                           files={"file": ("a.pdf", PDF, "application/pdf")})) == (400, "BAD_REQUEST")
    malformed = client.post(UP, headers=h(key="mp", **{"Content-Type": "multipart/form-data; boundary=zzz"}),
                            content=b"--zzz\r\nContent-Disposition: form-data; name=\"file\"\r\n\r\nno end")
    assert err(malformed)[0] == 400
    assert version(client) == v


@pytest.mark.parametrize("method,path,status", [
    ("GET", "/api/unknown", 404),
    ("GET", f"/api/cases/{CASE}/context", 405),
    ("GET", f"/api/cases/{CASE}/proposals/P/accept", 405),
    ("POST", f"/api/cases/{CASE}", 405),
    ("POST", "/api/officer/queue", 405),
    ("DELETE", f"/api/cases/{CASE}", 405),
])
def test_api_routes_never_fall_through_to_spa(client, method, path, status):
    r = client.request(method, path, headers=h("OFFICER"))
    assert r.status_code == status and r.headers["content-type"].startswith("application/json")
    assert "<html" not in r.text.lower()


def test_spa_does_not_serve_files_outside_dist(client):
    for path in ("/..%2f..%2frequirements.txt", "/%2e%2e/%2e%2e/boussla/services.py", "/assets/../../../.env"):
        r = client.get(path)
        assert "OPENAI" not in r.text and "streamlit==" not in r.text and "BousslaAppService" not in r.text


def test_internal_errors_are_generic(client, svc, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret detail C:\\Users\\x\\runtime\\cases.sqlite")
    monkeypatch.setattr(svc, "get_case", boom)
    r = client.get(f"/api/cases/{CASE}", headers=h(key=None))
    assert r.status_code == 500 and "secret detail" not in r.text and "Traceback" not in r.text


def test_company_cannot_reach_officer_data(client):
    assert err(client.get("/api/officer/queue", headers=h(key=None))) == (403, "FORBIDDEN")
    body = client.get(f"/api/cases/{CASE}", headers=h(key=None)).json()
    for field in ("findings", "score", "hypotheses", "candidate_passages", "reference_note", "proposals"):
        assert field not in body
    assert "local_path" not in str(body)


def test_double_submit_with_fresh_keys_writes_once(client):
    v = version(client, "OFFICER")
    draft = client.post(f"/api/cases/{CASE}/clarifications/prepare", headers=h("OFFICER"),
                        json={"expected_version": v}).json()
    url = f"/api/cases/{CASE}/clarifications/{draft['draft_id']}/publish"
    first = client.post(url, headers=h("OFFICER", "click-1"), json={"expected_version": v})
    second = client.post(url, headers=h("OFFICER", "click-2"), json={"expected_version": v})
    assert first.status_code == 200 and err(second) == (409, "STALE_REVISION")
    assert len(client.get(f"/api/cases/{CASE}", headers=h("OFFICER", None)).json()["requests"]) == 1


def test_stale_browser_version_is_surfaced(client):
    stale = version(client)
    client.post(CTX, headers=h(key="other-tab"), json={"expected_version": stale, "context": {
        "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "autre onglet", "beneficiary_type": "X"}})
    r = client.post(CTX, headers=h(key="this-tab"), json={"expected_version": stale, "context": {
        "purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "cet onglet", "beneficiary_type": "X"}})
    assert err(r) == (409, "STALE_REVISION") and version(client) == stale + 1


def test_importing_the_asgi_module_builds_nothing():
    """`boussla.web.app:app` must not build the service (read .env, open Qdrant/OpenAI
    clients, create runtime/) at import time; that happens at server startup."""
    import boussla.web.app as web
    assert web.app.state.service is None
