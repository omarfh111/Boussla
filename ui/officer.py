"""Officer views using only officer-scoped service results."""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import streamlit as st

from boussla.contracts import Audience, OfficerCaseView, ProposalStatus
from ui.common import amount, service_action


FIXTURE_DOCUMENTS = Path(__file__).resolve().parents[1] / "docs" / "build_lock" / "fixtures" / "documents"


def bundled_mock_document(local_path: str, expected_sha256: str) -> bytes | None:
    """Expose only bundled fixture PDFs, never arbitrary service paths or URLs."""
    candidate = (Path(__file__).resolve().parents[1] / "docs" / "build_lock" / local_path).resolve()
    if candidate.suffix.lower() != ".pdf" or not candidate.is_relative_to(FIXTURE_DOCUMENTS.resolve()):
        return None
    if not candidate.is_file():
        return None
    content = candidate.read_bytes()
    return content if sha256(content).hexdigest() == expected_sha256 else None


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
    st.dataframe([{
        "Vue": observation.perspective.value,
        "Facture": observation.invoice_number,
        "Émetteur indiqué": observation.issuer_company_id or "Inconnu",
        "Acheteur indiqué": observation.buyer_company_id or "Inconnu",
        "Date": observation.issued_on.isoformat(),
        "Montant TTC": amount(observation.gross_millimes),
        "Source": observation.document_id,
        "Origine": observation.origin_group_id,
    } for observation in case.invoice_observations], hide_index=True, width="stretch")
    st.caption("Les vues acheteur et vendeur concernent une même opération ; elles ne sont pas additionnées.")
    st.markdown("#### Références de quantité")
    for reference in case.quantity_references:
        st.write(f"{reference.reference_id} · {reference.project_id} · {reference.quantity} {reference.unit} · {reference.baseline_kind.value} · {reference.acceptance_status}")
        st.caption("Sources : " + (", ".join(reference.source_refs) if reference.source_refs else "non indiquées"))
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
        st.write(f"{doc.original_filename} · {doc.acquisition_channel.value} · origine {doc.origin_group_id} · SHA-256 {doc.sha256[:12]}…")
        if case.mode.value == "MOCK":
            content = bundled_mock_document(doc.local_path, doc.sha256)
            if content is not None:
                st.download_button("Télécharger la pièce synthétique", data=content, file_name=doc.original_filename,
                                   mime="application/pdf", key=f"download_{doc.document_id}")
    st.caption("Le contenu concordant et l'origine des fichiers sont deux questions distinctes. Une pièce non signée ou d'origine inconnue n'est pas classée fausse.")
    if case.candidate_passages:
        st.markdown("#### Passages de référence candidats")
        for passage in case.candidate_passages:
            st.write(f"{passage.document_title} · {passage.rule_id} · {passage.mode.value}")
            st.caption(passage.text)
        st.caption("Un passage retrouvé est un candidat ; son applicabilité requiert une revue humaine.")

    st.markdown("#### Matrice des hypothèses et sensibilité")
    if case.hypotheses:
        st.dataframe([{
            "Hypothèse": h.hypothesis_id,
            "Énoncé": h.statement_template_id,
            "Statut": h.status.value,
            "Pièces utiles": ", ".join(h.missing_evidence_types) if h.missing_evidence_types else "Aucune",
            "Portée": h.scope,
        } for h in case.hypotheses], hide_index=True, width="stretch")
    if case.scenarios:
        st.dataframe([{
            "Scénario": s.label,
            "Marge fictive": s.inputs.get("quantity_margin", s.inputs.get("margin", "N/D")),
            "Résidu calculé": s.outputs.get("residual_units", s.outputs.get("residual", "N/D")),
            "Unité": s.outputs.get("unit", "N/D"),
            "Statut": s.outputs.get("status", "HYPOTHETICAL"),
        } for s in case.scenarios], hide_index=True, width="stretch")
        st.caption("Calculs de sensibilité purement arithmétiques et hypothétiques : ne constituent pas une décision ni une modification du dossier.")

    st.markdown("#### Brouillons exportables du dossier")
    draft_audience_label = st.radio("Audience du brouillon", ["Interne (Agent)", "Destinataire (Entreprise)"],
                                    horizontal=True, key="draft_audience_selector")
    audience = Audience.OFFICER if "Interne" in draft_audience_label else Audience.COMPANY
    # Export is an explicit human action bound to the current version (logged by the service).
    if st.button("Générer le brouillon", key="generate_draft"):
        service_action(lambda: service.export_dossier(actor, case.case_id, audience, case.case_version),
                       on_success=lambda artifact: st.session_state.__setitem__("dossier_draft", artifact))
    draft = st.session_state.get("dossier_draft")
    if draft is not None and draft.case_id == case.case_id:
        if draft.case_version != case.case_version:
            st.warning("Ce brouillon appartient à une ancienne version. Générez-le à nouveau.")
        else:
            st.caption(f"{draft.disclaimer_fr} · {draft.filename}")
            with st.expander(f"Aperçu du brouillon ({draft.audience.value})", expanded=False):
                st.markdown(draft.content_markdown)
            st.download_button(f"Télécharger le brouillon ({draft.audience.value})", data=draft.content_markdown,
                               file_name=draft.filename, mime="text/markdown", key=f"dl_draft_{draft.audience.value}")

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
                                                                    case.case_version, f"ui:publish:{draft.draft_id}"),
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
        elif left.button("Accepter dans ce dossier", key=f"accept_{proposal.proposal_id}_v{case.case_version}"):
            service_action(lambda: service.accept_evidence(actor, case.case_id, proposal.proposal_id,
                                                          case.case_version, f"ui:decide:{proposal.proposal_id}:v{case.case_version}"),
                           on_success=lambda result: st.session_state.__setitem__("last_revision", result))
        if right.button("Rejeter la proposition", key=f"reject_{proposal.proposal_id}_v{case.case_version}"):
            service_action(lambda: service.reject_evidence(actor, case.case_id, proposal.proposal_id,
                                                          case.case_version, "Portée non retenue", f"ui:decide:{proposal.proposal_id}:v{case.case_version}"),
                           on_success=lambda result: st.session_state.__setitem__("last_revision", result))
    if not pending:
        st.caption("Aucune proposition en attente.")

    revision = st.session_state.get("last_revision")
    if revision is not None and revision.case_id == case.case_id:
        st.markdown("#### Avant / après la décision")
        st.write(f"Décision {revision.outcome} · version {revision.previous_version} → {revision.new_version} · {revision.mode.value}")
        before = revision.score_before.review_index if revision.score_before else None
        after = revision.score_after.review_index if revision.score_after else None

        c_rev1, c_rev2 = st.columns(2)
        with c_rev1:
            st.metric(f"Priorité avant révision (v{revision.previous_version})", before if before is not None else "N/D")
        with c_rev2:
            st.metric(f"Priorité après révision (v{revision.new_version})", after if after is not None else "N/D",
                      delta=f"{after - before}" if (before is not None and after is not None) else None,
                      delta_color="inverse")

        st.write(f"Priorité de revue : {before} → {after}")
        if revision.mode.value == "MOCK":
            st.caption("Valeurs recomputées par le service MOCK ; ne constituent pas une mesure des contrôles réels.")
        else:
            st.caption("Valeurs recalculées par les contrôles déterministes après acceptation ; la version précédente reste consultable.")
        changed = {a.allocation_id: a.quantity for a in revision.allocations_after}
        st.write("Affectations : " + ", ".join(f"{a.target_project_id} {a.quantity}" for a in revision.allocations_before)
                 + " → " + ", ".join(f"{a.target_project_id} {q}" for a in revision.allocations_after
                                     for q in [changed[a.allocation_id]]))

    history = service.get_history(actor, case.case_id)
    st.markdown("#### Historique du dossier")
    for item in history.revisions:
        st.write(f"Version {item.version} · {item.created_at.isoformat()} · {item.reason}")


def render_diagnostics(case: OfficerCaseView) -> None:
    st.subheader("Diagnostics et modes d'intégration")
    st.write(f"**Mode global du dossier :** `{case.mode.value}`")
    st.markdown("#### État par composant")
    for node, mode in case.mode_by_node.items():
        st.write(f"• **{node}** : `{mode.value}`")
    st.markdown("#### Comprendre les statuts")
    st.caption(
        "• **LIVE** : Exécuté avec les moteurs réels (base SQLite locale, calculs déterministes, modèle si configuré).\n\n"
        "• **TEMPLATE** : Remplacement déterministe ou gabarit contrôlé en cas de repli.\n\n"
        "• **MANUAL** : Mode manuel ou saisie utilisateur.\n\n"
        "• **NOT_RUN** : Composant non exécuté dans ce flux (mention transparente, aucun résultat inventé)."
    )
    if case.mode.value == "MOCK":
        st.info("Mesures de tests intégrés : NOT_RUN dans cette interface. Les chiffres du service MOCK sont des données de démonstration.")
    else:
        st.info("Mesures de tests intégrés : NOT_RUN dans cette interface. Les modes ci-dessus indiquent ce qui a réellement été exécuté.")
