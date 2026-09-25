"""Click-through tests of the Streamlit app on the REAL SQLite-backed service.

Every step goes through the app's forms and buttons; the service handle is used
only to assert persisted state. Providers are disabled (manual mode, no tracing).
"""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from boussla.config import FIXTURE_ROOT, get_settings
from boussla.contracts import Allocation, Mode, ProposalStatus, RequestStatus

APP = Path(__file__).resolve().parents[2] / "app.py"
CASE = "CASE-BRICKS-001"
INVOICE_PDF = (FIXTURE_ROOT / "documents" / "01_buyer_invoice.pdf").read_bytes()
ALLOCATION_PDF = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()


@pytest.fixture(autouse=True)
def real_env(tmp_path, monkeypatch):
    for key, name in (("CASE_DB_PATH", "cases.sqlite"), ("CHECKPOINT_DB_PATH", "cp.sqlite"),
                      ("UPLOAD_DIR", "uploads"), ("EVENT_LOG_PATH", "events.jsonl")):
        monkeypatch.setenv(key, str(tmp_path / name))
    monkeypatch.setenv("LLM_PROVIDER", "manual")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.delenv("BOUSSLA_SERVICE", raising=False)
    get_settings.cache_clear()
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()
    get_settings.cache_clear()


def start(role="Entreprise") -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    if role != "Entreprise":
        at.selectbox(key="demo_role").set_value(role).run()
        assert not at.exception, at.exception
    return at


def switch(at: AppTest, role: str) -> AppTest:
    at.selectbox(key="demo_role").set_value(role).run()
    assert not at.exception, at.exception
    return at


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label.startswith(label))


def svc(at: AppTest):
    return at.session_state["boussla_service"]


def version(at: AppTest) -> int:
    return svc(at).store.case_meta(CASE)["version"]


def publish_request(at: AppTest) -> str:
    switch(at, "Agent")
    at.button(key="prepare_request").click().run()
    at.button(key="publish_request").click().run()
    assert not at.exception, at.exception
    requests = svc(at).get_case(svc(at).registry.actors["DEMO-OFFICER"], CASE).requests
    return requests[-1].request.request_id


def respond_with_allocation(at: AppTest, request_id: str, attach: bool = True) -> None:
    switch(at, "Entreprise")
    at.text_area(key=f"answer_{request_id}").set_value("Nous proposons 1 000 unités pour P1 et 1 000 pour P2.")
    at.checkbox(key=f"allocation_{request_id}").set_value(True).run()
    if attach:
        next(u for u in at.file_uploader if u.key == f"response_file_{request_id}").set_value(
            ("affectation_P2.pdf", ALLOCATION_PDF, "application/pdf"))
    button(at, "Envoyer la réponse").click().run()
    assert not at.exception, at.exception


def test_real_banner_and_company_scope():
    at = start()
    banner = " ".join(i.value for i in at.info)
    assert "service réel" in banner and "service MOCK" not in banner
    assert svc(at).mode is Mode.LIVE
    assert not any(m.label == "Priorité de revue" for m in at.metric)  # no internal index for the company


def test_full_release_loop_through_the_ui():
    at = start()
    # Company: declared context through the form.
    v0 = version(at)
    inputs = {t.label: t for t in at.text_input}
    inputs["Précision sur l'usage"].set_value("Lot de maçonnerie P1")
    inputs["Bénéficiaire prévu"].set_value("Client du chantier")
    button(at, "Enregistrer le contexte déclaré").click().run()
    assert not at.exception, at.exception
    assert version(at) == v0 + 1
    assert any("Lot de maçonnerie P1" in m.value for m in at.markdown)

    # Company: invoice upload through the operations form.
    next(u for u in at.file_uploader if u.label.startswith("Facture")).set_value(
        ("facture_recue.pdf", INVOICE_PDF, "application/pdf"))
    button(at, "Déposer la pièce").click().run()
    assert not at.exception, at.exception
    assert version(at) == v0 + 2
    assert any("facture_recue.pdf" in m.value for m in at.markdown)

    # Officer: B's deterministic checks, index and dossier.
    switch(at, "Agent")
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Priorité de revue"] == "40"
    assert any("QUANTITY · UNRESOLVED" in m.value for m in at.markdown)
    at.button(key="generate_draft").click().run()
    assert any("Télécharger le brouillon" in d.label for d in at.download_button)

    # Clarification -> company response with document and reallocation.
    request_id = publish_request(at)
    respond_with_allocation(at, request_id)
    case = svc(at).get_case(svc(at).registry.actors["DEMO-OFFICER"], CASE)
    proposal = next(p for p in case.proposals if p.status is ProposalStatus.AWAITING_HUMAN_REVIEW)
    assert proposal.source_document_id and {c.target_project_id: c.new_quantity for c in proposal.changes} == {"P1": "1000", "P2": "1000"}
    assert case.requests[-1].request.status is RequestStatus.RESPONDED

    # Officer acceptance -> new version, recomputed index, old version preserved.
    switch(at, "Agent")
    before = version(at)
    assert {m.label: m.value for m in at.metric}["Priorité de revue"] == "40"
    button(at, "Accepter dans ce dossier").click().run()
    assert not at.exception, at.exception
    assert version(at) == before + 1
    assert any("Priorité de revue : 40 → 0" in m.value for m in at.markdown)
    assert {m.label: m.value for m in at.metric}["Priorité de revue"] == "0"
    assert any(f"Version {before + 1}" in m.value for m in at.markdown)
    store = svc(at).store
    assert [(a.target_project_id, a.quantity) for a in store.facts(CASE, "allocation", Allocation, version=before)] == [("P1", "2000")]
    assert sorted((a.target_project_id, a.quantity) for a in store.facts(CASE, "allocation", Allocation)) == [("P1", "1000"), ("P2", "1000")]

    # Duplicate acceptance (same UI key) replays, no second revision.
    officer = svc(at).registry.actors["DEMO-OFFICER"]
    replay = svc(at).accept_evidence(officer, CASE, proposal.proposal_id, before, f"ui:decide:{proposal.proposal_id}:v{before}")
    assert replay.replayed and version(at) == before + 1


def test_statement_only_response_cannot_be_accepted():
    at = start()
    request_id = publish_request(at)
    respond_with_allocation(at, request_id, attach=False)
    switch(at, "Agent")
    assert not any(b.label == "Accepter dans ce dossier" for b in at.button)
    assert any("déclaration seule ne suffit pas" in w.value for w in at.warning)


def test_stale_page_click_does_not_approve():
    at = start()
    request_id = publish_request(at)
    respond_with_allocation(at, request_id)
    switch(at, "Agent")
    stale_accept = button(at, "Accepter dans ce dossier")
    # Another actor changes the case after the officer's page was rendered.
    company = svc(at).registry.actors["DEMO-COMPANY-BAT"]
    v = version(at)
    svc(at).submit_context(company, CASE, {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "mise à jour"}, v, "late")
    stale_accept.click().run()
    assert not at.exception, at.exception
    assert version(at) == v + 1  # only the company's change; no acceptance applied
    case = svc(at).get_case(svc(at).registry.actors["DEMO-OFFICER"], CASE)
    assert case.proposals[-1].status is ProposalStatus.AWAITING_HUMAN_REVIEW
    assert case.score.review_index == 40


def test_state_survives_app_restart():
    at = start()
    request_id = publish_request(at)
    v = version(at)
    st.cache_resource.clear()  # drop the in-process service: simulated restart
    at2 = start()
    assert version(at2) == v
    assert any(request_id in m.value for m in at2.markdown)  # company inbox still shows the request
    respond_with_allocation(at2, request_id)
    assert version(at2) == v + 2  # attachment upload + response


def test_repeated_reruns_are_read_only():
    at = start()
    store = svc(at).store
    v, events = version(at), len(store.events(CASE))
    for role in ("Entreprise", "Agent", "Entreprise", "Agent"):
        switch(at, role)
        at.run()
    assert version(at) == v and len(store.events(CASE)) == events


def test_double_clicks_do_not_duplicate_actions():
    at = start()
    switch(at, "Agent")
    at.button(key="prepare_request").click().run()
    publish = at.button(key="publish_request")
    publish.click().run()
    v = version(at)
    publish.click().run()  # second click on the same (now published) draft
    assert not at.exception, at.exception
    assert version(at) == v
    officer = svc(at).registry.actors["DEMO-OFFICER"]
    assert len(svc(at).get_case(officer, CASE).requests) == 1

    request_id = svc(at).get_case(officer, CASE).requests[0].request.request_id
    respond_with_allocation(at, request_id)
    switch(at, "Agent")
    accept = button(at, "Accepter dans ce dossier")
    accept.click().run()
    v = version(at)
    accept.click().run()  # double click on accept
    assert not at.exception, at.exception
    assert version(at) == v
    assert [r.reason for r in svc(at).store.revisions(CASE)].count(
        next(r.reason for r in svc(at).store.revisions(CASE) if r.reason.startswith("Pièce acceptée"))) == 1
