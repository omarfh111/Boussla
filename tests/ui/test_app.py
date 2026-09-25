"""Smoke the real Streamlit entrypoint in both local role simulations."""

from streamlit.testing.v1 import AppTest
from pathlib import Path


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
