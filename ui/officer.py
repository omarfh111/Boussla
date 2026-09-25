"""Officer views using only officer-scoped service results."""

from datetime import datetime, timezone
from uuid import uuid4

import streamlit as st

from boussla.contracts import OfficerCaseView, ProposalStatus
from ui.common import amount, service_action


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


def render_dossier(service, actor, case: OfficerCaseView) -> None:
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

    st.markdown("#### Hypothèses et sensibilité")
    for hypothesis in case.hypotheses:
        st.write(f"{hypothesis.statement_template_id} · {hypothesis.status.value}")
        if hypothesis.missing_evidence_types:
            st.caption("Pièces encore utiles : " + ", ".join(hypothesis.missing_evidence_types))
    for scenario in case.scenarios:
        st.write(f"{scenario.label} · hypothétique · ne modifie pas le dossier")
        st.json(scenario.outputs)

    st.markdown("#### Demande de précision")
    if st.button("Préparer une demande neutre", key="prepare_request"):
        service_action(lambda: service.prepare_clarification(actor, case.case_id, case.case_version),
                       on_success=lambda draft: st.session_state.__setitem__("clarification_draft", draft))
    draft = st.session_state.get("clarification_draft")
    if draft is not None:
        if draft.case_version != case.case_version:
            st.warning("Le brouillon appartient à une ancienne version. Préparez une nouvelle demande.")
        else:
            st.write(draft.text_fr)
            if st.button("Publier dans la boîte de démo", key="publish_request"):
                service_action(lambda: service.publish_clarification(actor, case.case_id, draft.draft_id,
                                                                    case.case_version, str(uuid4())),
                               on_success=lambda _: st.session_state.pop("clarification_draft", None))

    st.markdown("#### Révision des pièces proposées")
    pending = [p for p in case.proposals if p.status is ProposalStatus.AWAITING_HUMAN_REVIEW]
    for proposal in pending:
        st.write(f"**{proposal.proposal_id}** · transaction {proposal.transaction_id} · source {proposal.source_document_id or 'déclaration seule'}")
        for change in proposal.changes:
            st.write(f"{change.target_project_id or change.target_type.value} : {change.old_quantity or '0'} → {change.new_quantity} {proposal.unit}")
        st.caption("Proposition en attente : le constat et l'indice ne changent qu'après acceptation par le service.")
        left, right = st.columns(2)
        if proposal.source_document_id is None:
            left.warning("Aucune pièce jointe : une déclaration seule ne suffit pas à accepter cette répartition.")
        elif left.button("Accepter dans ce dossier", key=f"accept_{proposal.proposal_id}"):
            service_action(lambda: service.accept_evidence(actor, case.case_id, proposal.proposal_id,
                                                          case.case_version, str(uuid4())),
                           on_success=lambda result: st.session_state.__setitem__("last_revision", result))
        if right.button("Rejeter la proposition", key=f"reject_{proposal.proposal_id}"):
            service_action(lambda: service.reject_evidence(actor, case.case_id, proposal.proposal_id,
                                                          case.case_version, "Portée non retenue", str(uuid4())),
                           on_success=lambda result: st.session_state.__setitem__("last_revision", result))
    if not pending:
        st.caption("Aucune proposition en attente.")

    revision = st.session_state.get("last_revision")
    if revision is not None and revision.case_id == case.case_id:
        st.markdown("#### Avant / après la décision")
        st.write(f"Décision {revision.outcome} · version {revision.previous_version} → {revision.new_version} · {revision.mode.value}")
        before = revision.score_before.review_index if revision.score_before else None
        after = revision.score_after.review_index if revision.score_after else None
        st.write(f"Priorité de revue : {before} → {after}")
        st.caption("Valeurs recomputées par le service MOCK ; ne constituent pas une mesure des contrôles réels.")

    history = service.get_history(actor, case.case_id)
    st.markdown("#### Historique du dossier")
    for item in history.revisions:
        st.write(f"Version {item.version} · {item.created_at.isoformat()} · {item.reason}")
