"""Conservative cited answers over one authorized case; no free-form model claims."""
from __future__ import annotations

from datetime import datetime, timezone
from pydantic import Field

from boussla.contracts import Contract, OfficerCaseView, OfficerHistoryView
from boussla.network import NetworkView

RULE_VERSION = "investigation-answer-1"
FAMILIES = {"QUANTITY": "écart de quantités", "SETTLEMENT": "écart de règlement",
            "COUNTERPARTY": "écart de contrepartie"}


class InvestigationCitation(Contract):
    source_id: str
    kind: str
    label_fr: str
    source_url: str | None = None


class InvestigationAnswer(Contract):
    case_id: str
    case_version: int
    question: str
    answer_fr: str
    citations: tuple[InvestigationCitation, ...] = ()
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rule_version: str = RULE_VERSION
    mode: str = "TEMPLATE"
    authoritative: bool = False
    limitations: tuple[str, ...] = ("Synthèse de faits sourcés ; l’agent vérifie les pièces et décide.",)


def answer_investigation(question: str, view: OfficerCaseView, history: OfficerHistoryView,
                         network: NetworkView) -> InvestigationAnswer:
    query = question.casefold()
    citations: list[InvestigationCitation] = []
    lines: list[str] = []

    def cite(source_id: str, kind: str, label: str, url: str | None = None) -> None:
        if source_id and source_id not in {item.source_id for item in citations}:
            citations.append(InvestigationCitation(source_id=source_id, kind=kind, label_fr=label, source_url=url))

    def priority() -> None:
        if view.triage is not None:
            lines.append(f"Urgence de traitement : {view.triage.triage_priority}/100 ; indice documentaire distinct : {view.score.review_index if view.score else 'inconnu'}.")
            cite(view.case_id, "CASE", f"Dossier {view.case_id} v{view.case_version}")
        for cause in sorted((view.score.cause_progress if view.score else ()),
                            key=lambda item: -float(item.current_contribution))[:3]:
            if float(cause.current_contribution) <= 0:
                continue
            lines.append(f"{FAMILIES.get(cause.family.value, cause.family.value)} : +{cause.current_contribution} pour {cause.transaction_id} ({cause.stage.value}).")
            cite(cause.cause_id, "CAUSE", f"Cause {cause.family.value} · {cause.transaction_id}")
            for source in cause.source_ids[:3]:
                cite(source, "FACT", f"Source de la cause {cause.cause_id}")
        for factor in view.history_signal_factors[:2]:
            lines.append(f"Signal historique distinct : {factor.explanation_fr}")
            for source in factor.source_signal_ids[:3]:
                cite(source, "HISTORY", "Signal historique")
        if view.triage:
            for code in view.triage.reason_codes[:3]:
                cite(code, "TRIAGE_RULE", f"Motif de triage {code}")

    if any(word in query for word in ("priorit", "urgent", "pourquoi", "score", "indice")):
        priority()
    elif any(word in query for word in ("histori", "habit", "délai", "evolution", "évolution")):
        profile = view.behavior_profile
        for metric in (profile.metrics if profile else ()):
            if metric.status != "AVAILABLE":
                continue
            lines.append(f"{metric.label_fr} : {metric.current_value} {metric.unit} observé contre {metric.baseline_value} {metric.unit} habituel ({metric.sample_size} mois couverts).")
            cite(f"{view.case_id}:METRIC:{metric.code}", "METRIC", f"Mesure {metric.label_fr} · {profile.rule_version}")
            for source in metric.source_ids[:3]:
                cite(source, "HISTORY", f"Source de {metric.label_fr}")
            if len(lines) >= 4:
                break
    elif any(word in query for word in ("document", "pièce", "preuve", "manqu")):
        for action in (view.recommended_actions or ())[:4]:
            if not action.required_documents and not action.source_ids:
                continue
            lines.append(f"{action.title_fr} : {action.reason}")
            cite(action.action_id, "ACTION", f"Action calculée {action.title_fr} · {action.rule_version}")
            for source in action.source_causes[:3]:
                cite(source, "CAUSE", "Cause de l’action")
            for source in action.source_ids[:3]:
                cite(source, "ACTION_SOURCE", f"Source de l’action {action.action_id}")
        if not lines:
            lines.append("Aucune pièce supplémentaire précisément identifiée dans cette version du dossier.")
            cite(view.case_id, "CASE", f"Dossier {view.case_id} v{view.case_version}")
    elif any(word in query for word in ("réseau", "reseau", "fournisseur", "relation", "entreprise")):
        edges = [edge for edge in network.edges if edge.kind == "SELLS_TO"][:5]
        node_names = {node.node_id: node.label for node in network.nodes}
        for edge in edges:
            lines.append(f"Relation enregistrée : {node_names.get(edge.source, edge.source)} vend à {node_names.get(edge.target, edge.target)} dans {edge.case_id}.")
            for source in edge.source_ids[:3]:
                cite(source, "TRANSACTION", f"Relation {edge.edge_id}")
    elif any(word in query for word in ("règle", "regle", "référence", "reference", "texte")):
        for passage in view.candidate_passages[:4]:
            lines.append(f"Référence candidate : {passage.document_title}, {passage.rule_id}{f', article {passage.article}' if passage.article else ''}. Applicabilité à vérifier.")
            cite(passage.rule_id, "REFERENCE", passage.document_title, passage.source_url)
    elif any(word in query for word in ("décision", "decision", "valid", "rejet")):
        for event in reversed(history.events):
            if event.kind not in {"EVIDENCE_ACCEPTED", "EVIDENCE_REJECTED", "RESPONSE"}:
                continue
            lines.append(f"{event.at.isoformat()} : {event.summary}")
            cite(event.event_id, "EVENT", f"Événement {event.kind}")
            for source in event.fact_ids[:2]:
                cite(source, "FACT", "Fait associé à la décision")
            if len(lines) >= 4:
                break
    else:
        priority()
    if not lines:
        lines.append("Données insuffisantes pour répondre à cette question à partir des sources de ce dossier.")
    return InvestigationAnswer(case_id=view.case_id, case_version=view.case_version,
                               question=question, answer_fr="\n".join(lines), citations=tuple(citations))
