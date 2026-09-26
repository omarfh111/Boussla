"""HTTP contract tests against the real versioned SQLite service."""
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
def client(tmp_path):
    settings = Settings(case_db_path=tmp_path / "case.sqlite", upload_dir=tmp_path / "up")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_demo_case(store)
    with TestClient(create_app(BousslaAppService(store, ActorRegistry.demo(), settings=settings))) as c:
        yield c


def headers(role="COMPANY", key=None):
    h = {"X-Boussla-Demo-Role": role}
    if key:
        h["Idempotency-Key"] = key
    return h


def view(client, role):
    r = client.get(f"/api/cases/{CASE}", headers=headers(role))
    assert r.status_code == 200, r.text
    return r.json()


def test_health_role_isolation_and_safe_serialization(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/demo/bootstrap", headers=headers()).json()["case_ids"] == [CASE]
    assert client.get("/api/demo/bootstrap", headers=headers("OTHER")).status_code == 403
    assert client.get("/api/demo/bootstrap", headers={"X-Boussla-Actor-Id": "DEMO-OFFICER"}).status_code == 403
    company, officer = view(client, "COMPANY"), view(client, "OFFICER")
    assert company["audience"] == "COMPANY" and "score" not in company
    assert "candidate_passages" not in company and "reference_note" not in company
    assert officer["score"]["review_index"] == 40
    assert "local_path" not in str(company) and "local_path" not in str(officer)
    assert client.get("/api/officer/queue", headers=headers()).status_code == 403
    assert client.get("/api/officer/queue", headers=headers("OFFICER")).json()["items"][0]["review_index"] == 40


def test_mutation_flow_stale_idempotent_and_history(client):
    v = view(client, "COMPANY")["case_version"]
    r = client.post(f"/api/cases/{CASE}/context", headers=headers(key="context-1"), json={
        "expected_version": v, "context": {"project_id": "P1", "purpose_category": "CONSTRUCTION_PROJECT",
                                            "purpose_text": "Maçonnerie", "beneficiary_type": "PROJECT"}})
    assert r.status_code == 200, r.text
    assert r.json()["case_version"] == v + 1
    assert client.post(f"/api/cases/{CASE}/context", headers=headers(key="context-2"), json={
        "expected_version": v, "context": {"purpose_category": "CONSTRUCTION_PROJECT"}}).json()["error"]["code"] == "STALE_REVISION"
    assert client.post(f"/api/cases/{CASE}/documents", headers=headers(key="bad-file"),
                       data={"expected_version": v + 1}, files={"file": ("bad.txt", b"x", "text/plain")}).json()["error"]["code"] == "UNSUPPORTED_FILE"
    v = view(client, "OFFICER")["case_version"]
    d = client.post(f"/api/cases/{CASE}/clarifications/prepare", headers=headers("OFFICER", "prepare-1"),
                    json={"expected_version": v}).json()
    assert d["questions"]
    url = f"/api/cases/{CASE}/clarifications/{d['draft_id']}/publish"
    r = client.post(url, headers=headers("OFFICER", "publish-1"), json={"expected_version": v})
    assert r.status_code == 200, r.text
    req = r.json()["request"]["request_id"]
    assert client.post(url, headers=headers("OFFICER", "publish-1"), json={"expected_version": v}).json()["request"]["request_id"] == req
    v = view(client, "COMPANY")["case_version"]
    r = client.post(f"/api/cases/{CASE}/documents", headers=headers(key="upload-1"),
                    data={"expected_version": v}, files={"file": ("allocation.pdf", PDF, "application/pdf")})
    assert r.status_code == 200, r.text
    assert "local_path" not in r.text
    doc = r.json()["document"]["document_id"]
    v = view(client, "COMPANY")["case_version"]
    response = {"answers": {"Q-PROJECT-ALLOCATION": "1000 P1 et 1000 P2"},
                "document_ids": [doc], "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001",
                                                  "splits": {"P1": "1000", "P2": "1000"}}}
    r = client.post(f"/api/cases/{CASE}/responses/{req}", headers=headers(key="response-1"),
                    json={"expected_version": v, "response": response})
    assert r.status_code == 200, r.text
    proposal = r.json()["proposal_ids"][0]
    assert view(client, "OFFICER")["score"]["review_index"] == 40
    v = view(client, "OFFICER")["case_version"]
    url = f"/api/cases/{CASE}/proposals/{proposal}/accept"
    assert client.post(url, headers=headers(key="wrong-role"), json={"expected_version": v}).status_code == 403
    accepted = client.post(url, headers=headers("OFFICER", "accept-1"), json={"expected_version": v})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["score_before"]["review_index"] == 40
    assert accepted.json()["score_after"]["review_index"] == 0
    assert client.post(url, headers=headers("OFFICER", "accept-1"), json={"expected_version": v}).json()["replayed"]
    assert len(client.get(f"/api/cases/{CASE}/history", headers=headers("OFFICER")).json()["revisions"]) > 1
