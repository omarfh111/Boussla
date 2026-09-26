"""Company views using only the company-scoped service result."""

from decimal import Decimal, InvalidOperation
from uuid import uuid4

import streamlit as st

from boussla.contracts import CompanyCaseView, PurposeCategory
from ui.common import amount, service_action


def _valid_quantity(value: str) -> bool:
    try:
        quantity = Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return False
    return quantity.is_finite() and quantity >= 0


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


def render_context(service, actor, case: CompanyCaseView) -> None:
    st.subheader("Contexte et réponses")
    st.caption("Contexte déclaré par l'entreprise ; il ne prouve pas à lui seul l'usage réel.")
    for project in case.projects:
        start = project.planned_start.isoformat() if project.planned_start else "date inconnue"
        end = project.planned_end.isoformat() if project.planned_end else "date inconnue"
        st.write(f"**{project.label}** · {start} → {end} · {project.status}")
    for claim in case.context_claims:
        st.write(f"{claim.purpose_text} · bénéficiaire : {claim.beneficiary_type} · {claim.verification_status}")
    with st.form("company_context"):
        project_labels = {p.project_id: p.label for p in case.projects}
        selected_project = st.selectbox("Projet concerné", list(project_labels), format_func=lambda key: project_labels[key]) if project_labels else None
        purpose = st.selectbox("Usage prévu", list(PurposeCategory), format_func=lambda category: {
            PurposeCategory.RESALE: "Revente", PurposeCategory.OPERATING_USE: "Exploitation",
            PurposeCategory.LONG_LIVED_ASSET: "Actif durable", PurposeCategory.CONSTRUCTION_PROJECT: "Projet de construction",
            PurposeCategory.OTHER_OR_UNKNOWN: "Autre ou inconnu",
        }[category])
        description = st.text_input("Précision sur l'usage")
        beneficiary = st.text_input("Bénéficiaire prévu")
        current_project = next((p for p in case.projects if p.project_id == selected_project), None)
        planned_start = st.date_input("Début prévu", value=current_project.planned_start if current_project else None)
        planned_end = st.date_input("Fin prévue", value=current_project.planned_end if current_project else None)
        stage = st.text_input("Phase du projet", value="")
        submitted = st.form_submit_button("Enregistrer le contexte déclaré")
    if submitted:
        if not description.strip() or not beneficiary.strip():
            st.warning("Précisez l'usage et le bénéficiaire.")
        elif planned_start and planned_end and planned_end < planned_start:
            st.warning("La fin prévue doit être postérieure au début prévu.")
        else:
            payload = {"project_id": selected_project, "purpose_category": purpose.value,
                       "purpose_text": description.strip(), "beneficiary_type": beneficiary.strip(),
                       "planned_start": planned_start, "planned_end": planned_end, "stage": stage.strip() or None}
            service_action(lambda: service.submit_context(actor, case.case_id, payload, case.case_version, str(uuid4())))

    if case.inbox:
        st.markdown("#### Boîte de demandes")
        for request in case.inbox:
            status_fr = {
                "PUBLISHED_IN_DEMO": "En attente de votre réponse",
                "RESPONDED": "Réponse transmise",
                "CLOSED": "Clôturée",
            }.get(request.request.status.value, request.request.status.value)
            st.markdown(f"**Demande {request.request.request_id}** · statut : `{status_fr}` ({request.request.status.value})")
            st.info(request.text_fr)
            if request.request.status.value == "PUBLISHED_IN_DEMO":
                with st.form(f"response_{request.request.request_id}"):
                    answer = st.text_area("Votre réponse", key=f"answer_{request.request.request_id}")
                    attachment = st.file_uploader("Pièce d'affectation, si disponible (PDF)", type=["pdf"], key=f"response_file_{request.request.request_id}")
                    allocation = st.checkbox("Proposer une répartition entre les deux lots de la démo", key=f"allocation_{request.request.request_id}")
                    lots = [p.project_id for p in case.projects][:2]
                    p1 = st.text_input(f"Quantité {lots[0]}" if lots else "Quantité lot 1", value="1000", key=f"p1_{request.request.request_id}") if allocation else None
                    p2 = st.text_input(f"Quantité {lots[1]}" if len(lots) > 1 else "Quantité lot 2", value="1000", key=f"p2_{request.request.request_id}") if allocation else None
                    send = st.form_submit_button("Envoyer la réponse dans la boîte de démo")
                if send:
                    if not answer.strip():
                        st.warning("Rédigez une réponse avant l'envoi.")
                    elif allocation and (not _valid_quantity(p1) or not _valid_quantity(p2)):
                        st.warning("Indiquez des quantités positives ou nulles pour les deux lots.")
                    elif allocation and (len(lots) < 2 or not case.allocations):
                        st.warning("Aucune affectation ou aucun second lot connu : répondez sans répartition.")
                    else:
                        def submit():
                            version = case.case_version
                            ids = []
                            if attachment is not None:
                                document = service.upload_document(actor, case.case_id, attachment.getvalue(), attachment.name,
                                                                   "application/pdf", version, str(uuid4()))
                                ids.append(document.document.document_id)
                                version = document.case_version
                            payload = {"answers": {q.question_id: answer.strip() for q in request.questions},
                                       "document_ids": ids}
                            if allocation:
                                current = case.allocations[0]  # the company's own recorded allocation line
                                payload["allocation"] = {"transaction_id": current.transaction_id,
                                                         "line_id": current.line_id,
                                                         "splits": {lots[0]: p1.strip(), lots[1]: p2.strip()}}
                            return service.submit_response(actor, case.case_id, request.request.request_id,
                                                           payload, version, str(uuid4()))
                        service_action(submit)
    if case.responses:
        st.markdown("#### Réponses enregistrées")
        for response in case.responses:
            st.write(f"{response.response_id} · {response.submitted_at.isoformat()} · pièces : {len(response.document_ids)}")
    else:
        if not case.inbox:
            st.info("Aucune demande publiée pour ce dossier.")
