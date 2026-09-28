"""Five independently explained officer indicators, composed without new scoring."""
from __future__ import annotations

from datetime import datetime
from boussla.contracts import CaseIndicator, IndicatorFactor, OfficerCaseView
from boussla.triage import SIGNAL_REASON

FAMILIES = {"QUANTITY": "Affectation des quantités", "COUNTERPARTY": "Concordance des factures", "SETTLEMENT": "Règlement observé"}
STAGES = {"UNRESOLVED": "à expliquer", "EXPLANATION_RECEIVED": "réponse reçue", "EVIDENCE_RECEIVED": "pièce reçue",
          "EVIDENCE_COHERENT": "cohérence vérifiée, validation requise", "RESOLVED": "résolue par l’agent"}
URGENCY = {"REVIEW_INDEX_BASE": "Contribution documentaire de base", "REVIEW_FINDING_PRESENT": "Un écart reste à expliquer",
           "CLARIFICATION_PENDING": "Demande en attente de réponse", "CLARIFICATION_OVERDUE": "Cible de réponse dépassée",
           "REPEATED_UNANSWERED_CLARIFICATION": "Plusieurs demandes échues sans réponse",
           "EVIDENCE_AWAITING_OFFICER_DECISION": "Pièce en attente de décision de l’agent",
           "ACTIVITY_GAP_NEEDS_REVIEW": "Interruption d’activité à examiner",
           "HISTORICAL_DATA_GAP_NEEDS_REVIEW": "Historique incomplet à compléter",
           "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW": "Incohérences répétées à examiner",
           "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW": "Écart au comportement habituel à examiner"}


def urgency_sources(view, code):
    if code.startswith("REVIEW_"):
        return tuple(c.cause_id for c in view.score.cause_progress)
    if code == "EVIDENCE_AWAITING_OFFICER_DECISION":
        return tuple(p.proposal_id for p in view.proposals if p.status.value == "AWAITING_HUMAN_REVIEW")
    if code in ("CLARIFICATION_PENDING", "CLARIFICATION_OVERDUE", "REPEATED_UNANSWERED_CLARIFICATION"):
        return tuple(d.request_id for d in view.clarification_deadlines
                     if d.status.value in ("PUBLISHED_IN_DEMO", "EXTENDED")
                     and (code == "CLARIFICATION_PENDING" or d.overdue))
    return tuple(s.signal_id for s in view.history_signals if SIGNAL_REASON.get(s.reason_code) == code)


def case_indicators(view: OfficerCaseView, as_of: datetime) -> dict[str, CaseIndicator]:
    score = view.score
    review = CaseIndicator(value=str(score.review_index) if score.review_index is not None else None,
        status="INSUFFICIENT_DATA" if score.review_index is None else
               "PROVISIONAL" if any(c.provisional for c in score.cause_progress) else "AVAILABLE",
        factors=tuple(IndicatorFactor(code=c.cause_id or f"{c.transaction_id}:{c.family.value}",
            value=c.raw_contribution, contribution=c.current_contribution, source_ids=c.source_ids,
            explanation=f"{FAMILIES[c.family.value]} · {STAGES[c.stage.value]}")
            for c in score.cause_progress),
        explanation="Maximum des indices par transaction ; les contributions se somment uniquement au sein d’une transaction."
                    " Une réduction provisoire ne résout pas le constat.",
        calculated_at=score.calculated_at or score.cutoff, rule_version=score.rules_version,
        sample_size=len({c.transaction_id for c in score.cause_progress}) or len(view.transactions))
    coverage = CaseIndicator(value=score.evidence_coverage,
        status="INSUFFICIENT_DATA" if score.evidence_coverage is None else
               "AVAILABLE" if score.coverage_complete else "PARTIAL",
        factors=tuple(IndicatorFactor(code=f.value, value="1" if f in score.tested_families else None,
            explanation="Contrôle évaluable" if f in score.tested_families else "Prérequis manquants")
            for f in dict.fromkeys((*score.tested_families, *score.unknown_families))),
        explanation="Part des contrôles applicables évaluables ; une couverture complète ne signifie pas absence d’écart.",
        calculated_at=score.calculated_at or score.cutoff, rule_version="evidence-coverage-v4-1",
        sample_size=len(score.tested_families) + len(score.unknown_families))
    history = CaseIndicator(value=str(view.history_signal_index) if view.history_signal_index is not None else None,
        status=view.history_signal_status,
        factors=tuple(IndicatorFactor(code=f.reason_code.value, contribution=str(f.contribution),
            source_ids=f.source_signal_ids, explanation=f.explanation_fr) for f in view.history_signal_factors),
        explanation="Comparaison avec les périodes couvertes de cette entreprise ; aucun effet sur la revue documentaire.",
        calculated_at=as_of, rule_version=view.history_signal_method or "HISTORY_CONTEXT_V1",
        sample_size=len({p for signal in view.history_signals for p in signal.baseline_periods}))
    triage = view.triage
    urgency = CaseIndicator(value=str(triage.triage_priority) if triage else None,
        status="AVAILABLE" if triage else "INSUFFICIENT_DATA",
        factors=tuple(IndicatorFactor(code=code, contribution=str(points),
            source_ids=urgency_sources(view, code), explanation=URGENCY.get(code, code))
            for code, points in (triage.components.items() if triage else ())),
        explanation="Priorité de traitement plafonnée à 100 ; les délais et l’historique ne modifient pas le constat documentaire.",
        calculated_at=triage.as_of if triage else as_of,
        rule_version=triage.formula_version if triage else "triage-demo-1",
        sample_size=len(view.requests) + len(view.proposals) + len(view.history_signals))
    confidence = CaseIndicator(value=str(view.operational_confidence_index)
                              if view.operational_confidence_index is not None else None,
        status="LIMITED_DATA" if view.operational_confidence_index is not None and view.operational_confidence_data_quality == "LIMITED_DATA" else view.operational_confidence_status,
        factors=tuple(IndicatorFactor(code=f.code, value=str(f.numerator), contribution=f.weighted_contribution,
            source_ids=f.source_ids, explanation=f"{f.explanation_fr} ({f.numerator}/{f.denominator} ; poids {f.effective_weight} %)")
            for f in view.operational_confidence_factors),
        explanation="Coopération et corroboration observées ; sans effet sur la revue ni l’urgence. " + view.operational_confidence_sample_note_fr,
        calculated_at=view.operational_confidence_as_of or as_of,
        rule_version=view.operational_confidence_method,
        sample_size=view.operational_confidence_sample_size)
    return {"document_review": review, "evidence_coverage": coverage,
            "historical_signal": history, "urgency": urgency, "operational_confidence": confidence}
