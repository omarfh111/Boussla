"""Smoke the real Streamlit entrypoint in both local role simulations."""

from streamlit.testing.v1 import AppTest
from pathlib import Path
from uuid import uuid4

from boussla.mock_service import demo_actors


APP = Path(__file__).resolve().parents[2] / "app.py"


def test_company_view_shows_own_operations_without_internal_index():
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Mes opérations", "Contexte et réponses"]
    assert any("simulation de rôles" in item.value for item in app.info)
    assert not any("Priorité de revue" in item.label for item in app.metric)
    assert app.dataframe


def test_officer_view_shows_queue_and_supported_finding():
    app = AppTest.from_file(APP).run()
    app.selectbox[0].set_value("Agent").run()
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["File de revue", "Dossier"]
    assert any(item.label == "Priorité de revue" for item in app.metric)
    assert any("QUANTITY" in item.value for item in app.markdown)


def test_company_response_without_document_stays_pending_for_officer():
    app = AppTest.from_file(APP).run()
    app.selectbox[0].set_value("Agent").run()
    app.button(key="prepare_request").click().run()
    assert not app.exception
    app.button(key="publish_request").click().run()
    assert not app.exception

    app.selectbox[0].set_value("Entreprise").run()
    assert app.text_area
    app.text_area[0].set_value("Je propose 1 000 unités pour chaque lot.")
    next(item for item in app.checkbox if item.label.startswith("Proposer une répartition")).set_value(True)
    app.run()
    next(item for item in app.button if item.label.startswith("Envoyer la réponse")).click().run()
    assert not app.exception

    app.selectbox[0].set_value("Agent").run()
    assert not app.exception
    assert not any(item.label == "Accepter dans ce dossier" for item in app.button)
    assert any("déclaration seule ne suffit pas" in item.value for item in app.warning)


def test_officer_accepts_document_backed_proposal_and_sees_revision():
    app = AppTest.from_file(APP).run()
    service = app.session_state["boussla_service"]
    actors = demo_actors()
    case_id = service.case_id
    version = service.version
    draft = service.prepare_clarification(actors["officer"], case_id, version)
    request = service.publish_clarification(actors["officer"], case_id, draft.draft_id, version, str(uuid4()))
    document = service.upload_document(actors["company"], case_id, b"%PDF-1.4", "allocation.pdf",
                                       "application/pdf", service.version, str(uuid4()))
    service.submit_response(actors["company"], case_id, request.request.request_id,
                            {"answers": {}, "document_ids": [document.document.document_id],
                             "allocation": {"P1": "1000", "P2": "1000"}}, service.version, str(uuid4()))
    version_before = service.version
    app.selectbox[0].set_value("Agent").run()
    next(item for item in app.button if item.label == "Accepter dans ce dossier").click().run()
    assert not app.exception
    assert service.version == version_before + 1
    assert any("Priorité de revue : 40 → 0" in item.value for item in app.markdown)
