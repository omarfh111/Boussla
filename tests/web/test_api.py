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


def test_link_existing_upload_to_answered_response(client):
    officer = view(client, "OFFICER")
    draft = client.post(f"/api/cases/{CASE}/clarifications/prepare",
        headers=headers("OFFICER", "link-prepare"),
        json={"expected_version": officer["case_version"]}).json()
    published = client.post(f"/api/cases/{CASE}/clarifications/{draft['draft_id']}/publish",
        headers=headers("OFFICER", "link-publish"),
        json={"expected_version": officer["case_version"]}).json()
    request_id = published["request"]["request_id"]
    company = view(client, "COMPANY")
    answered = client.post(f"/api/cases/{CASE}/responses/{request_id}",
        headers=headers("COMPANY", "link-answer"),
        json={"expected_version": company["case_version"],
              "response": {"answers": {"Q-PROJECT-ALLOCATION": "P1 1000, P2 1000"},
                           "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001",
                                          "splits": {"P1": "1000", "P2": "1000"}}}})
    assert answered.status_code == 200, answered.text
    response_id = answered.json()["response"]["response_id"]
    assert view(client, "OFFICER")["score"]["review_index"] == 30
    company = view(client, "COMPANY")
    uploaded = client.post(f"/api/cases/{CASE}/documents", headers=headers("COMPANY", "link-upload"),
        data={"expected_version": company["case_version"]},
        files={"file": ("allocation.pdf", PDF, "application/pdf")})
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document"]["document_id"]
    version = view(client, "COMPANY")["case_version"]
    url = f"/api/cases/{CASE}/responses/by-id/{response_id}/documents"
    payload = {"expected_version": version, "document_id": document_id}
    assert client.post(url, headers=headers("OFFICER", "link-officer"), json=payload).status_code == 403
    linked = client.post(url, headers=headers("COMPANY", "link-existing"), json=payload)
    assert linked.status_code == 200, linked.text
    assert linked.json()["response"]["document_ids"] == [document_id]
    assert view(client, "OFFICER")["score"]["review_index"] == 20
    assert client.post(url, headers=headers("COMPANY", "link-existing"), json=payload).json() == linked.json()


def test_health_role_isolation_and_safe_serialization(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/demo/bootstrap", headers=headers()).json()["case_ids"] == [CASE]
    assert client.get("/api/demo/bootstrap", headers=headers("OTHER")).status_code == 403
    assert client.get("/api/demo/bootstrap", headers={"X-Boussla-Actor-Id": "DEMO-OFFICER"}).status_code == 403
    assert client.post(f"/api/cases/{CASE}/context", headers=headers(key="forged"), json={
        "expected_version": 1, "actor_id": "DEMO-OFFICER", "context": {}}).status_code == 403
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
    assert view(client, "OFFICER")["score"]["review_index"] == 20
    v = view(client, "OFFICER")["case_version"]
    url = f"/api/cases/{CASE}/proposals/{proposal}/accept"
    assert client.post(url, headers=headers(key="wrong-role"), json={"expected_version": v}).status_code == 403
    accepted = client.post(url, headers=headers("OFFICER", "accept-1"), json={"expected_version": v})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["score_before"]["review_index"] == 20
    assert accepted.json()["score_before"]["raw_review_index"] == 40
    assert accepted.json()["score_after"]["review_index"] == 0
    assert client.post(url, headers=headers("OFFICER", "accept-1"), json={"expected_version": v}).json()["replayed"]
    assert len(client.get(f"/api/cases/{CASE}/history", headers=headers("OFFICER")).json()["revisions"]) > 1
    assert client.get(f"/api/cases/{CASE}/audit", headers=headers()).status_code == 403
    audit = client.get(f"/api/cases/{CASE}/audit", headers=headers("OFFICER")).json()
    decision = next(record for record in audit["records"] if record["action"] == "EVIDENCE_ACCEPTED")
    assert decision["actor_id"] == "DEMO-OFFICER"
    assert decision["before"]["review_index"] == 20
    assert decision["after"]["review_index"] == 0
    assert decision["evidence_ids"] == [proposal]
    proposal_change = next(change for change in decision["fact_changes"] if change["kind"] == "proposal")
    assert proposal_change["before"]["status"] == "AWAITING_HUMAN_REVIEW"
    assert proposal_change["after"]["status"] == "ACCEPTED"
    assert "local_path" not in str(decision)
    assert decision["rules_version"] and decision["engine_version"]
    assert sum(record["action"] == "EVIDENCE_ACCEPTED" for record in audit["records"]) == 1


def test_upload_can_attach_to_existing_response(client):
    v = view(client, "OFFICER")["case_version"]
    draft = client.post(f"/api/cases/{CASE}/clarifications/prepare", headers=headers("OFFICER"),
                        json={"expected_version": v}).json()
    request = client.post(f"/api/cases/{CASE}/clarifications/{draft['draft_id']}/publish",
                          headers=headers("OFFICER", "publish-later"),
                          json={"expected_version": v}).json()["request"]
    v = view(client, "COMPANY")["case_version"]
    response = client.post(f"/api/cases/{CASE}/responses/{request['request_id']}",
                           headers=headers(key="respond-later"), json={"expected_version": v, "response": {
                               "answers": {"Q-PROJECT-ALLOCATION": "1000 P1, 1000 P2"},
                               "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001",
                                              "splits": {"P1": "1000", "P2": "1000"}},
                           }})
    assert response.status_code == 200, response.text
    response_id = response.json()["response"]["response_id"]
    v = view(client, "COMPANY")["case_version"]
    upload = client.post(f"/api/cases/{CASE}/documents", headers=headers(key="upload-later"),
                         data={"expected_version": v, "response_id": response_id},
                         files={"file": ("allocation.pdf", PDF, "application/pdf")})
    assert upload.status_code == 200, upload.text
    assert upload.json()["case_version"] == v + 1

def test_notification_feed_is_role_scoped_and_event_backed(client):
    url = f"/api/cases/{CASE}/notifications"
    assert client.get(url).status_code == 403
    company = client.get(url, headers=headers()).json()
    officer = client.get(url, headers=headers("OFFICER")).json()
    assert company["audience"] == "COMPANY" and officer["audience"] == "OFFICER"
    assert "score" not in str(company).lower()
    version = view(client, "OFFICER")["case_version"]
    draft = client.post(f"/api/cases/{CASE}/clarifications/prepare",
                        headers=headers("OFFICER", "notification-draft"),
                        json={"expected_version": version}).json()
    sent = client.post(f"/api/cases/{CASE}/clarifications/{draft['draft_id']}/publish",
                       headers=headers("OFFICER", "notification-publish"),
                       json={"expected_version": version})
    assert sent.status_code == 200, sent.text
    company = client.get(url, headers=headers()).json()
    assert any(item["kind"] == "REQUEST_PUBLISHED" for item in company["items"])
    assert all(item["status"] == "RECORDED" for item in company["items"])

def test_network_http_routes_enforce_officer_scope(client):
    assert client.get("/api/network", headers=headers()).status_code == 403
    all_cases = client.get("/api/network", headers=headers("OFFICER"))
    assert all_cases.status_code == 200, all_cases.text
    graph = all_cases.json()
    assert graph["scope"] == "ALL" and graph["nodes"] and graph["edges"]
    assert "local_path" not in all_cases.text
    case = client.get(f"/api/network/case/{CASE}", headers=headers("OFFICER"))
    assert case.status_code == 200 and case.json()["scope_id"] == CASE
    company = client.get("/api/network/company/DEMO-BAT", headers=headers("OFFICER"))
    assert company.status_code == 200 and company.json()["scope"] == "COMPANY"
    assert client.get("/api/network/case/CASE-NOT-ASSIGNED", headers=headers("OFFICER")).status_code == 403

def test_investigation_http_answer_is_grounded_and_role_scoped(client):
    url = f"/api/cases/{CASE}/investigate"
    assert client.post(url, headers=headers(), json={"question": "Pourquoi prioritaire ?"}).status_code == 403
    response = client.post(url, headers=headers("OFFICER"), json={"question": "Pourquoi prioritaire ?"})
    assert response.status_code == 200, response.text
    answer = response.json()
    assert answer["mode"] == "TEMPLATE" and answer["citations"]
    assert answer["authoritative"] is False and "local_path" not in response.text
    assert client.post(url, headers=headers("OFFICER"), json={"question": "x"}).json()["error"]["code"] == "INVALID_INPUT"


def test_case_review_decision_http_role_reason_and_replay(client):
    path = f"/api/cases/{CASE}/decisions"
    version = view(client, "OFFICER")["case_version"]
    payload = {"expected_version": version, "kind": "ESCALATE", "reason": "Vérification renforcée demandée"}
    assert client.post(path, headers=headers(key="company-decision"), json=payload).status_code == 403
    assert client.post(path, headers=headers("OFFICER", "short-reason"), json={**payload, "reason": "court"}).status_code == 400
    first = client.post(path, headers=headers("OFFICER", "escalate-http"), json=payload)
    assert first.status_code == 200, first.text
    assert first.json()["kind"] == "ESCALATE" and first.json()["case_version"] == version + 1
    replay = client.post(path, headers=headers("OFFICER", "escalate-http"), json=payload)
    assert replay.status_code == 200 and replay.json()["decision_id"] == first.json()["decision_id"]
    assert view(client, "OFFICER")["case_version"] == version + 1
    assert "case_decisions" not in view(client, "COMPANY")
