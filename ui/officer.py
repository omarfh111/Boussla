"""Officer views using only officer-scoped service results."""

from datetime import datetime, timezone

import streamlit as st

from boussla.contracts import OfficerCaseView
from ui.common import amount


def render_queue(service, actor) -> None:
    st.subheader("File de revue")
    page = service.list_queue(actor, datetime.now(timezone.utc), 20)
    st.caption(f"Données synthétiques · service {page.mode.value} · index de priorité, pas probabilité de fraude")
    if page.items:
        st.dataframe([{
            "Dossier": item.case_id,
            "Entreprise": item.company_display_name,
            "Version": item.case_version,
            "Priorité": item.review_index if item.review_index is not None else "Non calculée",
            "Couverture": item.evidence_coverage or "Inconnue",
            "Constats actifs": item.active_finding_count,
            "Clarification": item.clarification_status.value,
            "Portée": item.scope_note,
        } for item in page.items], hide_index=True, width="stretch")
    else:
        st.info("Aucun dossier assigné.")


def render_dossier(case: OfficerCaseView) -> None:
    st.subheader(f"Dossier {case.case_id}")
    st.caption(f"{case.company_display_name} · version {case.case_version} · {case.mode.value}")
    score = case.score
    if score:
        left, middle, right = st.columns(3)
        left.metric("Priorité de revue", score.review_index if score.review_index is not None else "N/D")
        middle.metric("Couverture des preuves", score.evidence_coverage or "N/D")
        right.metric("Clarification", score.clarification_status.value)
        st.caption(score.scope_note)

    st.markdown("#### Rapprochement des observations")
    for tx in case.transactions:
        st.write(f"**{tx.invoice_number or tx.transaction_id}** · facturé {amount(tx.invoiced_gross_millimes)} · réglé observé {amount(tx.settled_millimes)} · déclaré {amount(tx.declared_millimes)}")
        st.caption(f"Origine : {tx.corroboration_status} · opération {tx.transaction_id}")
    st.markdown("#### Constats à examiner")
    for finding in case.findings:
        st.write(f"{finding.family.value} · {finding.status.value} · {finding.reason_code or 'Motif non précisé'}")
        if finding.quantity_difference is not None:
            st.caption(f"Écart de quantité : {finding.quantity_difference} {finding.unit or ''} · calcul {finding.calculation_version}")
    if not case.findings:
        st.info("Aucun constat disponible dans cette version.")

    st.markdown("#### Pièces et provenance")
    for item in case.documents:
        doc = item.document
        st.write(f"{doc.original_filename} · {doc.acquisition_channel.value} · origine {doc.origin_group_id}")
    st.caption("Le contenu concordant et l'origine des fichiers sont deux questions distinctes. Une pièce non signée ou d'origine inconnue n'est pas classée fausse.")
