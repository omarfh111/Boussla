"""Conservative cited answers over one authorized case; no free-form model claims."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from pydantic import Field

from boussla.contracts import Contract, OfficerCaseView, OfficerHistoryView, DocumentText
from boussla.network import NetworkView

RULE_VERSION = "investigation-answer-4"
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
                         network: NetworkView, document_texts: tuple[DocumentText, ...] = (),
                         audit_records: tuple[dict, ...] = ()) -> InvestigationAnswer:
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

    decision_terms = ("décision", "decision", "valid", "rejet", "accept", "preuve")
    score_terms = ("score", "indice", "contribution", "effet", "changé", "changement")
    if any(word in query for word in decision_terms) and any(word in query for word in score_terms):
        relevant = [record for record in audit_records
                    if record["action"] in {"EVIDENCE_ACCEPTED", "EVIDENCE_REJECTED"}
                    or record["action"].startswith("CASE_REVIEW_")]
        for record in reversed(relevant[-3:]):
            before = (record.get("before") or {}).get("review_index")
            after = (record.get("after") or {}).get("review_index")
            transition = (f"{before} → {after}" if before is not None and after is not None
                          else "variation inconnue faute de calcul figé")
            lines.append(f"Décision {record['action']} (v{record['case_version']}) : indice documentaire {transition}.")
            cite(record["audit_id"], "AUDIT", f"Journal de décision {record['action']}")
            for source in record.get("evidence_ids", ())[:3]:
                cite(source, "FACT", f"Fait lié à {record['audit_id']}")
            if record.get("rules_version"):
                cite(record["rules_version"], "RULE_VERSION", "Version des règles du calcul")
        if not lines:
            lines.append("Aucune décision comparable enregistrée dans le journal de ce dossier.")
            cite(view.case_id, "CASE", f"Dossier {view.case_id} v{view.case_version}")
    elif any(word in query for word in ("priorit", "urgent", "pourquoi", "score", "indice")):
        priority()
    elif any(word in query for word in ("histori", "habit", "délai", "evolution", "évolution")):
        profile = view.behavior_profile
        for signal in (profile.signals if profile else ())[:2]:
            lines.append(signal.explanation_fr)
            cite(f"{view.case_id}:SIGNAL:{signal.code}:{signal.currency or 'ALL'}", "HISTORY_SIGNAL",
                 f"Signal descriptif {signal.metric_code} · {signal.rule_version}")
            for source in signal.source_ids[:3]:
                cite(source, "HISTORY", f"Source du signal {signal.code}")
        for metric in (profile.metrics if profile else ()):
            if metric.status != "AVAILABLE":
                continue
            lines.append(f"{metric.label_fr} : {metric.current_value} {metric.unit} observé contre {metric.baseline_value} {metric.unit} habituel ({metric.sample_size} mois couverts).")
            cite(f"{view.case_id}:METRIC:{metric.code}", "METRIC", f"Mesure {metric.label_fr} · {profile.rule_version}")
            for source in metric.source_ids[:3]:
                cite(source, "HISTORY", f"Source de {metric.label_fr}")
            if len(lines) >= 4:
                break
    elif any(word in query for word in ("document", "pièce", "preuve", "manqu", "analyse", "contrôle", "authenticité", "facture", "mention")):
        document_question = any(word in query for word in ("analyse", "analys", "contrôle", "authenticité", "cohérence"))
        named_documents = [item for item in view.documents if item.document.document_id.casefold() in query]
        if document_question or named_documents:
            reports = named_documents or [item for item in view.documents if item.analysis is not None]
            for item in reports[:3]:
                report = item.analysis
                if report is None:
                    lines.append(f"Pièce {item.document.document_id} : aucun rapport d’analyse enregistré pour cette version.")
                else:
                    confidence = (f"{report.confidence.level} ({report.confidence.value}/100)"
                                  if report.confidence and report.confidence.value is not None else "données insuffisantes")
                    lines.append(f"Pièce {report.document_id} : classe proposée {report.classification} ; confiance documentaire {confidence}. {report.authenticity_statement}.")
                    cite(report.document_id, "DOCUMENT", f"Rapport documentaire · {report.rule_version}")
                    for check in (c for c in report.checks if c.status in ("FAIL", "WARN", "UNKNOWN")):
                        lines.append(f"Contrôle {check.code} : {check.status} — {check.explanation_fr}")
                        for source in check.source_ids[:2]:
                            cite(source, "DOCUMENT_CHECK_SOURCE", f"Source du contrôle {check.code}")
                        if len(lines) >= 8:
                            break
                    for cause_id in report.linked_cause_ids[:3]:
                        cite(cause_id, "CAUSE", f"Cause liée à la pièce {report.document_id}")
                    if report.limitations:
                        lines.append("Limites : " + " ; ".join(report.limitations[:2]))
                if len(lines) >= 8:
                    break
        if any(word in query for word in ("mention", "contient", "dit", "facture", "référence")) or named_documents:
            stop = {"quel", "quelle", "quels", "quelles", "dans", "pour", "avec", "document", "pièce", "facture",
                    "mentionne", "contient", "analyse", "texte", "page", "cette", "fait", "source"}
            terms = [term for term in re.findall(r"[\w-]{4,}", query) if term not in stop]
            passages = []
            for item in document_texts:
                if item.status not in ("OK", "PARTIAL"):
                    continue
                for page in item.pages:
                    for line in page.text.splitlines():
                        line = line.strip()
                        hits = sum(term in line.casefold() for term in terms)
                        if hits and line:
                            passages.append((hits, item.document_id, page.page, line[:180]))
            for _, document_id, page, line in sorted(passages, key=lambda value: (-value[0], value[1], value[2]))[:2]:
                lines.append(f"Extrait natif non vérifié de {document_id}, page {page} : « {line} »")
                cite(f"{document_id}:p{page}", "DOCUMENT_PAGE", f"Texte natif de {document_id}, page {page}")
        for action in (() if named_documents else (view.recommended_actions or ())[:4]):
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
            if event.kind not in {"EVIDENCE_ACCEPTED", "EVIDENCE_REJECTED", "RESPONSE"} and not event.kind.startswith("CASE_REVIEW_"):
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
