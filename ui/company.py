"""Company views using only the company-scoped service result."""

from uuid import uuid4

import streamlit as st

from boussla.contracts import CompanyCaseView
from ui.common import amount, service_action


def render_operations(service, actor, case: CompanyCaseView) -> None:
    st.subheader("Mes opérations")
    st.caption(f"Dossier {case.case_id} · version {case.case_version} · {case.mode.value}")
    st.write("Déposez une facture et, si disponible, une autre pièce justificative. Deux fichiers transmis par la même entreprise gardent la même origine déclarée.")
    with st.form("company_upload", clear_on_submit=True):
        uploaded = st.file_uploader("Facture ou pièce justificative (PDF, 10 Mo max)", type=["pdf"])
        unavailable = st.checkbox("La deuxième pièce n'est pas disponible pour le moment")
        submitted = st.form_submit_button("Déposer la pièce")
    if submitted:
        if uploaded is None:
            st.info("Choisissez une pièce PDF, ou indiquez que la deuxième pièce est indisponible.")
        else:
            service_action(lambda: service.upload_document(
                actor, case.case_id, uploaded.getvalue(), uploaded.name,
                "application/pdf", case.case_version, str(uuid4()),
            ))
    if unavailable:
        st.info("Deuxième pièce : indisponible. Le dossier peut continuer avec cette limite visible.")

    st.markdown("#### Facturé et réglé observé")
    if case.transactions:
        st.dataframe([{
            "Opération": tx.transaction_id,
            "Facture": tx.invoice_number or "Inconnue",
            "Date": tx.issued_on.isoformat() if tx.issued_on else "Inconnue",
            "Contrepartie": tx.counterparty_display_name or "Inconnue",
            "Facturé": amount(tx.invoiced_gross_millimes),
            "Réglé observé": amount(tx.settled_millimes),
            "Déclaré": amount(tx.declared_millimes),
            "Origines": "Distinctes enregistrées" if tx.corroboration_status.startswith("DISTINCT") else "Origine commune ou inconnue",
        } for tx in case.transactions], hide_index=True, width="stretch")
        st.caption("Les montants facturés, réglés et déclarés sont des vues séparées. Une origine distincte enregistrée n'authentifie pas une pièce.")
    else:
        st.info("Aucune opération visible dans ce dossier.")

    st.markdown("#### Pièces du dossier")
    for item in case.documents:
        doc = item.document
        st.write(f"{doc.original_filename} · {doc.acquisition_channel.value} · origine {doc.origin_group_id} · {item.mode.value}")
    if not case.documents:
        st.info("Aucune pièce reçue.")


def render_context(case: CompanyCaseView) -> None:
    st.subheader("Contexte et réponses")
    st.caption("Contexte déclaré par l'entreprise ; il ne prouve pas à lui seul l'usage réel.")
    for project in case.projects:
        start = project.planned_start.isoformat() if project.planned_start else "date inconnue"
        end = project.planned_end.isoformat() if project.planned_end else "date inconnue"
        st.write(f"**{project.label}** · {start} → {end} · {project.status}")
    for claim in case.context_claims:
        st.write(f"{claim.purpose_text} · bénéficiaire : {claim.beneficiary_type} · {claim.verification_status}")
    if case.inbox:
        st.markdown("#### Boîte de demandes")
        for request in case.inbox:
            st.write(f"{request.request.request_id} · {request.request.status.value}")
            st.write(request.text_fr)
    else:
        st.info("Aucune demande publiée pour ce dossier.")
