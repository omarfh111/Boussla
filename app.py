"""Single-app local demonstration on the real SQLite-backed service.

Set ``BOUSSLA_SERVICE=mock`` to run the in-memory MOCK service instead.
"""

import os

import streamlit as st

from boussla.contracts import Mode
from ui.company import render_context, render_operations
from ui.officer import render_diagnostics, render_dossier, render_queue


CASE_ID = "CASE-BRICKS-001"
COMPANY_ACTOR_ID = "DEMO-COMPANY-BAT"
OFFICER_ACTOR_ID = "DEMO-OFFICER"
st.set_page_config(page_title="Boussla · démonstration", layout="wide")


@st.cache_resource
def get_service():
    """One service per process; all state lives in the SQLite case store."""
    if os.environ.get("BOUSSLA_SERVICE", "").lower() == "mock":
        from boussla.mock_service import MockBousslaService
        return MockBousslaService()
    from boussla.services import build_service
    return build_service()


service = get_service()
st.session_state["boussla_service"] = service  # handle for tests/diagnostics
actors = service.registry.actors if hasattr(service, "registry") else None
if actors is None:  # MOCK service keeps its own demo roster
    from boussla.mock_service import demo_actors
    mock_actors = demo_actors()
    actors = {COMPANY_ACTOR_ID: mock_actors["company"], OFFICER_ACTOR_ID: mock_actors["officer"]}

st.title("Boussla")
if service.mode is Mode.MOCK:
    st.info("Données synthétiques · simulation de rôles locale, sans authentification · service MOCK. "
            "Les constats et indices du service sont des valeurs de démonstration, non des contrôles réels.")
else:
    st.info("Données synthétiques · simulation de rôles locale, sans authentification · service réel "
            "(base locale SQLite). Constats et indice calculés par les contrôles déterministes ; "
            "indice de priorité de revue, pas une probabilité de fraude.")
role = st.selectbox("Simulation de rôles", ["Entreprise", "Agent"], key="demo_role")
actor = actors[COMPANY_ACTOR_ID if role == "Entreprise" else OFFICER_ACTOR_ID]
case = service.get_case(actor, CASE_ID)

if role == "Entreprise":
    operations, context = st.tabs(["Mes opérations", "Contexte et réponses"])
    with operations:
        render_operations(service, actor, case)
    with context:
        render_context(service, actor, case)
else:
    queue, dossier, diagnostics = st.tabs(["File de revue", "Dossier", "Diagnostics"])
    with queue:
        render_queue(service, actor)
    with dossier:
        render_dossier(service, actor, case)
    with diagnostics:
        render_diagnostics(case)
