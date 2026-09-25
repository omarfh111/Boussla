"""Single-app local demonstration. Replace only the service adapter for integration."""

import streamlit as st

from boussla.mock_service import MockBousslaService, demo_actors
from ui.company import render_context, render_operations
from ui.officer import render_diagnostics, render_dossier, render_queue


CASE_ID = "CASE-BRICKS-001"
st.set_page_config(page_title="Boussla · démonstration", layout="wide")

if "boussla_service" not in st.session_state:
    st.session_state.boussla_service = MockBousslaService()
service = st.session_state.boussla_service
actors = demo_actors()

st.title("Boussla")
st.info("Données synthétiques · simulation de rôles locale, sans authentification · service MOCK. Les constats et indices du service sont des valeurs de démonstration, non des contrôles réels.")
role = st.selectbox("Simulation de rôles", ["Entreprise", "Agent"], key="demo_role")
actor = actors["company" if role == "Entreprise" else "officer"]
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
