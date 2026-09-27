"""Final release wiring: lane B portfolio in the real service, Enterprise 360, triage,
deterministic scenarios, demo-operator administration and HTTP role isolation."""
from datetime import timedelta

import pytest
from starlette.testclient import TestClient

from boussla.config import FIXTURE_ROOT, get_settings
from boussla.contracts import Allocation, BousslaError, ErrorCode, Perspective
from boussla.services import build_service
from boussla.store import utcnow
from boussla.web.app import create_app

BRICKS = "CASE-BRICKS-001"
PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setenv("BOUSSLA_PORTFOLIO", "true")
    get_settings.cache_clear()
    return build_service()


def actor(svc, name):
    return svc.registry.actors[name]


def officer(svc):
    return actor(svc, "DEMO-OFFICER")


def code(fn):
    with pytest.raises(BousslaError) as e:
        fn()
    return e.value.code


def all_items(svc):
    items, cursor = [], None
    while True:
        page = svc.list_queue(officer(svc), None, 5, cursor)
        items += page.items
        if page.next_cursor is None:
            return items
        cursor = page.next_cursor


def test_twelve_enterprise_portfolio_is_operational(svc):
    items = all_items(svc)  # paginated with the existing cursor contract
    portfolio = [i for i in items if i.case_id.startswith("SYN-OP-")]
    assert len(portfolio) == 12 and len(items) == 13 and BRICKS in {i.case_id for i in items}
    tx = obs = pairs = 0
    for item in portfolio:
        view = svc.get_case(officer(svc), item.case_id)
        assert len(view.transactions) >= 12 and view.enterprise_profile.data_kind == "SYNTHETIC"
        assert view.enterprise_profile.activity_start == "2025-01" and view.enterprise_profile.activity_end == "2025-12"
        assert view.financial_snapshot.label_fr == "Instantané financier synthétique — source autorisée simulée"
        assert view.financial_snapshot.inflows_millimes is None  # purchase ledger only, never a revenue claim
        tx += len(view.transactions)
        obs += len(view.invoice_observations)
        pairs += sum(c.status != "SINGLE_OBSERVATION" for c in view.invoice_comparisons)
        assert item.sector and item.synthetic_identifier.startswith("SYNTHETIC-MF-") and item.last_activity_at
    assert (tx, obs, pairs) == (147, 282, 135)
    # Authoritative order: triage desc, then review index desc (React never sorts by its own values).
    keys = [(-(i.triage_priority or 0), -(i.review_index if i.review_index is not None else -1)) for i in items]
    assert keys == sorted(keys)


def test_history_gap_raises_triage_not_review_index(svc):
    view = svc.get_case(officer(svc), "SYN-OP-005-CASE")
    months = {month.month: month for month in view.monthly_activity}
    assert len(months) == 12
    assert months["2025-09"].coverage_status == "COVERED" and months["2025-09"].transaction_count == 0
    assert months["2025-10"].coverage_status == "COVERED" and months["2025-10"].transaction_count == 0
    codes = {s.reason_code.value for s in view.history_signals}
    assert "ACTIVITY_GAP" in codes and all(s.affects_review_index is False for s in view.history_signals)
    gap = next(s for s in view.history_signals if s.reason_code.value == "ACTIVITY_GAP")
    assert gap.period == "2025-09/2025-10" and gap.explanation_fr
    assert view.score.review_index == 0 and "ACTIVITY_GAP_NEEDS_REVIEW" in view.triage.reason_codes
    assert view.triage.triage_priority > view.score.review_index
    assert not any("fraud" in s.explanation_fr.lower() for s in view.history_signals)


def test_historical_indicator_is_separate_explained_and_scoped(svc):
    view = svc.get_case(officer(svc), "SYN-OP-005-CASE")
    assert view.score.review_index == 0
    assert view.history_signal_status == "AVAILABLE"
    assert view.history_signal_index is not None and view.history_signal_index > 0
    assert view.history_signal_factors
    assert sum(f.contribution for f in view.history_signal_factors) >= view.history_signal_index
    assert all(f.source_signal_ids for f in view.history_signal_factors)
    item = next(i for i in all_items(svc) if i.case_id == view.case_id)
    assert item.history_signal_index == view.history_signal_index
    curated = svc.get_case(officer(svc), BRICKS)
    assert curated.history_signal_index is None
    assert curated.history_signal_status == "INSUFFICIENT_DATA"
    company = svc.get_case(actor(svc, "DEMO-COMPANY-BAT"), BRICKS).model_dump()
    assert "history_signal_index" not in company


def test_operational_confidence_is_unknown_without_interactions_and_officer_only(svc):
    officer_view = svc.get_case(officer(svc), BRICKS)
    assert officer_view.operational_confidence_index is None
    assert officer_view.operational_confidence_status == "INSUFFICIENT_DATA"
    assert officer_view.operational_confidence_eligible_observations == 0
    assert officer_view.operational_confidence_as_of is not None
    company_view = svc.get_case(actor(svc, "DEMO-COMPANY-BAT"), BRICKS).model_dump()
    assert "operational_confidence_index" not in company_view
    api = TestClient(create_app(svc), raise_server_exceptions=False)
    agent_body = api.get(f"/api/cases/{BRICKS}", headers={"X-Boussla-Demo-Role": "OFFICER"}).json()
    assert agent_body["operational_confidence_status"] == "INSUFFICIENT_DATA"
    assert "operational_confidence_factors" in agent_body
    company_body = api.get(f"/api/cases/{BRICKS}", headers={"X-Boussla-Demo-Role": "COMPANY"}).json()
    assert "operational_confidence_factors" not in company_body

    covered = svc.get_case(officer(svc), "SYN-OP-005-CASE")
    assert covered.operational_confidence_status == "AVAILABLE"
    assert covered.operational_confidence_eligible_observations >= 3
    historical_factor = next(f for f in covered.operational_confidence_factors
                             if f.code == "HISTORICAL_STABILITY")
    assert historical_factor.denominator >= 3 and historical_factor.source_ids
    assert covered.score.review_index == 0


def test_buyer_seller_comparison_is_field_level_and_neutral(svc):
    view = svc.get_case(officer(svc), "SYN-OP-003-CASE")
    diff = [c for c in view.invoice_comparisons if c.status == "DIFFERENCES"]
    assert len(diff) == 1 and diff[0].difference_fields == ("line.quantity", "line.unit_price_millimes")
    same = next(c for c in view.invoice_comparisons if c.status == "CONCORDANT")
    assert same.label_fr == "Observations concordantes"
    perspectives = {o.observation_id: o.perspective for o in view.invoice_observations}
    assert perspectives[same.buyer_observation_id] is Perspective.BUYER_RECEIVED
    assert perspectives[same.seller_observation_id] is Perspective.SELLER_ISSUED
    text = view.model_dump_json().lower()
    assert not any(w in text for w in ("déclaration validée", "facture authentique", "conformité prouvée"))


def test_brick_reallocation_scenario_is_deterministic_and_noncanonical(svc):
    before_v = svc.store.case_meta(BRICKS)["version"]
    before = [(a.target_project_id, a.quantity) for a in svc.store.facts(BRICKS, "allocation", Allocation)]
    view = svc.get_case(officer(svc), BRICKS)
    [sc] = [s for s in view.scenarios if ":REALLOCATION:" in s.scenario_id]
    assert sc.label == "Réaffectation hypothétique P1=1000 / P2=1000" and sc.hypothetical
    assert sc.outputs["current_review_index"] == "40" and sc.outputs["hypothetical_review_index"] == "0"
    assert sc.changes_canonical_state is False and view.score.review_index == 40
    margins = [s for s in view.scenarios if ":MARGIN:" in s.scenario_id]
    assert margins and all("hypothetical_review_index" not in s.outputs for s in margins)  # never invented
    assert svc.store.case_meta(BRICKS)["version"] == before_v
    assert [(a.target_project_id, a.quantity) for a in svc.store.facts(BRICKS, "allocation", Allocation)] == before


def test_investigator_on_portfolio_case_cites_history_codes(svc):
    view = svc.get_case(officer(svc), "SYN-OP-012-CASE")
    brief = view.investigator_brief
    assert brief is not None and 0 < len(brief.top_hypotheses) <= 5
    assert set(brief.history_signal_codes) == {s.reason_code.value for s in view.history_signals}
    assert any(o.text_fr.startswith("Historique synthétique observé") for o in brief.key_observations)
    assert view.score.review_index == 67  # unchanged by the assisted analysis


def test_no_project_durable_asset_context(svc):
    co = actor(svc, "DEMO-COMPANY-BAT")
    view = svc.submit_context(co, BRICKS, {
        "project_id": None, "purpose_category": "LONG_LIVED_ASSET",
        "purpose_text": "Achat de trois véhicules pour la flotte commerciale de l'entreprise.",
        "beneficiary_type": "Entreprise"}, svc.store.case_meta(BRICKS)["version"], "vehicles")
    claim = max(view.context_claims, key=lambda c: c.submitted_at)
    assert claim.project_id is None and claim.purpose_category.value == "LONG_LIVED_ASSET"
    assert view.capabilities.supports_null_project_id is True


def test_automatic_request_carries_reason_and_follow_up_state(svc):
    co = actor(svc, "DEMO-COMPANY-BAT")
    svc.submit_context(co, BRICKS, {"project_id": "P1", "purpose_category": "CONSTRUCTION_PROJECT",
                                    "purpose_text": "Lots P1 et P2", "beneficiary_type": "Projet"},
                       svc.store.case_meta(BRICKS)["version"], "ctx")
    [req] = svc.get_case(co, BRICKS).inbox
    assert req.request.origin == "AUTOMATIC" and req.request.overdue_state == "ON_TRACK"
    assert "PROJECT_ALLOCATION_EXCEEDS_REFERENCE" in req.request.reason_codes
    assert req.request.reason_text_fr == "Précisions demandées automatiquement à partir des informations disponibles."
    now = utcnow()
    svc.clock = lambda: now + timedelta(days=9)
    late = svc.get_case(officer(svc), BRICKS)
    assert late.requests[0].request.overdue_state == "FOLLOW_UP_DUE" and late.score.review_index == 40
    stored = svc.store.facts(BRICKS, "request", type(req))[0]
    assert stored.request.overdue_state is None  # read-time only, never persisted


# ---------------------------------------------------------------- administration
def test_admin_is_operator_only_and_synthetic_only(svc):
    co, op = actor(svc, "DEMO-COMPANY-BAT"), actor(svc, "DEMO-OPERATOR")
    for who in (co, officer(svc)):
        assert code(lambda: svc.admin_list_enterprises(who)) is ErrorCode.FORBIDDEN
        assert code(lambda: svc.admin_reset_portfolio(who, "RESET")) is ErrorCode.FORBIDDEN
        assert code(lambda: svc.admin_delete_enterprise(who, "SYN-OP-001", "SYN-OP-001")) is ErrorCode.FORBIDDEN
    assert code(lambda: svc.list_queue(op, None, 5)) is ErrorCode.FORBIDDEN  # operator is not an officer
    assert len(svc.admin_list_enterprises(op)) == 12
    for target in ("DEMO-BAT", "CASE-BRICKS-001", "../SYN-OP-001", "SYN-OP-999", "syn-op-001"):
        assert code(lambda: svc.admin_delete_enterprise(op, target, target)) is ErrorCode.NOT_FOUND
    assert code(lambda: svc.admin_delete_enterprise(op, "SYN-OP-001", "yes")) is ErrorCode.INVALID_INPUT
    assert code(lambda: svc.admin_reset_portfolio(op, "")) is ErrorCode.INVALID_INPUT
    assert svc.store.case_exists(BRICKS) and len(svc.admin_list_enterprises(op)) == 12


def test_admin_add_delete_reset_cycle(svc):
    op = actor(svc, "DEMO-OPERATOR")
    added = svc.admin_add_enterprise(op, {"display_name": "Atelier Test", "sector": "Services"}, "add-1")
    again = svc.admin_add_enterprise(op, {"display_name": "Atelier Test", "sector": "Services"}, "add-1")
    assert added == again and added.display_name == "SYNTHÉTIQUE — Atelier Test" and added.transaction_count == 0
    assert added.case_id in {i.case_id for i in all_items(svc)}
    assert code(lambda: svc.admin_add_enterprise(op, {"display_name": "x", "sector": "y", "company_id": "Z"}, "k")) \
        in (ErrorCode.INVALID_INPUT,)
    result = svc.admin_delete_enterprise(op, added.company_id, added.company_id)
    assert result.enterprise_count == 12 and not svc.store.case_exists(added.case_id)
    assert added.case_id not in officer(svc).assigned_case_ids
    # A company-side change to a portfolio case is discarded by an explicit reset only.
    svc.admin_delete_enterprise(op, "SYN-OP-001", "SYN-OP-001")
    assert len(svc.admin_list_enterprises(op)) == 11
    reset = svc.admin_reset_portfolio(op, "RESET")
    assert reset.enterprise_count == 12 and svc.store.case_exists("SYN-OP-001-CASE")
    assert len([i for i in all_items(svc) if i.case_id.startswith("SYN-")]) == 12
    assert svc.store.case_exists(BRICKS)  # the curated case is never touched by portfolio admin


# ---------------------------------------------------------------- HTTP boundary
def test_http_roles_admin_and_forged_outputs(svc):
    client = TestClient(create_app(svc), raise_server_exceptions=False)
    op = {"X-Boussla-Demo-Role": "OPERATOR"}
    boot = client.get("/api/demo/bootstrap", headers=op).json()
    assert boot["role"] == "DEMO_OPERATOR" and boot["demo_admin"]["can_delete"] is True and boot["case_ids"] == []
    for role in ("COMPANY", "OFFICER"):
        h = {"X-Boussla-Demo-Role": role}
        assert client.get("/api/demo/bootstrap", headers=h).json()["demo_admin"]["can_reset"] is False
        assert client.get("/api/admin/enterprises", headers=h).status_code == 403
        assert client.post("/api/admin/portfolio/reset", headers=h, json={"confirm": "RESET"}).status_code == 403
        assert client.request("DELETE", "/api/admin/enterprises/SYN-OP-001", headers=h,
                              json={"confirm": "SYN-OP-001"}).status_code == 403
    assert client.get("/api/admin/enterprises", headers={"X-Boussla-Demo-Role": "DEMO-OPERATOR"}).status_code == 403
    assert client.get("/api/officer/queue", headers=op).status_code == 403
    listing = client.get("/api/admin/enterprises", headers=op).json()
    assert len(listing["items"]) == 12 and listing["notice_fr"].startswith("Administration de données synthétiques")
    assert client.post("/api/admin/enterprises", headers={**op, "Idempotency-Key": "a1"},
                       json={"display_name": "Test", "sector": "Services"}).status_code == 200
    assert client.request("DELETE", "/api/admin/enterprises/..%2F..%2Fetc", headers=op,
                          json={"confirm": "x"}).status_code in (400, 404, 405)  # never reaches deletion
    # Company scope and forged server outputs.
    co = {"X-Boussla-Demo-Role": "COMPANY"}
    assert client.get("/api/cases/SYN-OP-001-CASE", headers=co).status_code == 403
    body = client.get(f"/api/cases/{BRICKS}", headers=co).json()
    for field in ("triage", "investigator_brief", "history_signals", "findings", "score", "enterprise_profile"):
        assert field not in body
    v = body["case_version"]
    for forged in ({"review_index": 0}, {"triage_priority": 0}, {"investigator_brief": {}}, {"triage": {}}):
        r = client.post(f"/api/cases/{BRICKS}/context", headers={**co, "Idempotency-Key": "f"},
                        json={"expected_version": v, "context": {"purpose_text": "x", **forged}})
        assert r.status_code == 403


# ---------------------------------------------------------------- JUDGE-054 through the service
@pytest.mark.parametrize("claim", ["This law definitely applies to this company.",
                                   "Cette règle s’applique au dossier."])
def test_definitive_applicability_note_is_dropped_but_passages_kept(tmp_path, claim):
    import json as _json

    import httpx

    from boussla.config import Settings
    from boussla.retrieval.corpus import load_public_references
    from boussla.retrieval.grounded_rag import OpenAIReferenceNoteGenerator, ReferenceAssistant
    from boussla.retrieval.lexical import LexicalReferenceRetriever
    from boussla.security import ActorRegistry
    from boussla.services import BousslaAppService
    from boussla.store import CaseStore
    from tests.integration.test_reference_service import CPTY, seed_counterparty_case

    def handler(request):
        refs = _json.loads(_json.loads(request.content)["input"][1]["content"])["references"]
        content = {"claims": [{"text_fr": claim, "rule_ids": [refs[0]["rule_id"]]}],
                   "applicability_questions": ["La version de la source est-elle applicable ?"]}
        return httpx.Response(200, json={"status": "completed", "model": "m", "output": [
            {"content": [{"type": "output_text", "text": _json.dumps(content)}]}]})

    settings = Settings(case_db_path=tmp_path / "c.sqlite", upload_dir=tmp_path / "u")
    store = CaseStore(settings.case_db_path, settings.upload_dir)
    seed_counterparty_case(store)
    generator = OpenAIReferenceNoteGenerator(api_key="test-only", model="m",
                                             client=httpx.Client(transport=httpx.MockTransport(handler)))
    svc = BousslaAppService(store, ActorRegistry.demo(), settings=settings, reference_assistant=ReferenceAssistant(
        LexicalReferenceRetriever(load_public_references()), generator))
    svc.registry.assign("DEMO-OFFICER", CPTY)
    view = svc.get_case(svc.registry.actors["DEMO-OFFICER"], CPTY)
    assert view.candidate_passages and view.reference_note is None
    assert view.score.review_index == svc.evaluate(CPTY).score.review_index
    assert "candidate_passages" not in svc.get_case(svc.registry.actors["DEMO-COMPANY-BAT"], CPTY).model_dump()
