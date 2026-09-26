"""Allowlisted clarification questions — lane A.

The planner (deterministic or model-assisted) may only select IDs from this
catalogue; it never writes free-form questions, deadlines or legal demands.
Wording is neutral: a question is a request for context, not an accusation.
"""
from __future__ import annotations

from boussla.contracts import DocumentClass, FindingFamily, FindingStatus, Question

QUESTIONS: dict[str, Question] = {q.question_id: q for q in (
    Question(question_id="Q-PROJECT-ALLOCATION", answer_kind="QUANTITY",
             text_fr="Les quantités de cette facture sont-elles toutes affectées au même lot de travaux ? "
                     "Sinon, indiquez les autres lots autorisés et les quantités correspondantes."),
    Question(question_id="Q-SUPPORTING-DOC", answer_kind="DOCUMENT",
             text_fr="Pouvez-vous joindre la pièce d'affectation ou de référence correspondante, si elle existe ?"),
    Question(question_id="Q-PURPOSE", answer_kind="CHOICE",
             choices=("RESALE", "OPERATING_USE", "LONG_LIVED_ASSET", "CONSTRUCTION_PROJECT", "OTHER_OR_UNKNOWN"),
             text_fr="Pour quel usage cet achat est-il prévu (revente, usage courant, immobilisation, chantier, autre) ?"),
    Question(question_id="Q-PROJECT-DATES", answer_kind="DATE_RANGE",
             text_fr="Quelle est la période d'utilisation prévue (date de début et de fin) pour ce projet ?"),
    Question(question_id="Q-STOCK", answer_kind="QUANTITY",
             text_fr="Une partie de cet achat est-elle conservée en stock ? Si oui, quelle quantité ?"),
    Question(question_id="Q-COUNTERPART-RECORD", answer_kind="DOCUMENT",
             text_fr="Disposez-vous d'un autre justificatif de cette opération (bon de livraison, relevé du fournisseur) ?"),
    # Project-context questions (lane C context layer; fixed IDs and wording, never model-written).
    Question(question_id="Q-HORIZON-CONFIRM", answer_kind="CHOICE", choices=("SHORT_HORIZON", "LONGER_HORIZON"),
             text_fr="Les éléments fournis sur la durée du projet ne concordent pas entièrement. Pouvez-vous confirmer "
                     "la période prévue : courte (90 jours ou moins) ou plus longue ?"),
    Question(question_id="Q-PROJECT-STAGE", answer_kind="TEXT",
             text_fr="À quelle phase du projet cet achat est-il rattaché ?"),
    Question(question_id="Q-PROJECT-BENEFICIARY", answer_kind="TEXT",
             text_fr="Quel projet, lot ou bénéficiaire est concerné par cet achat ?"),
    Question(question_id="Q-PROJECT-REFERENCE", answer_kind="DOCUMENT",
             text_fr="Disposez-vous d'une pièce ou référence décrivant l'affectation prévue de cet achat ?"),
)}

ALLOWED_RESPONSE_DOCUMENTS = (DocumentClass.ALLOCATION_RESPONSE, DocumentClass.ALLOCATION_REFERENCE,
                              DocumentClass.DELIVERY_RECORD, DocumentClass.OTHER_OR_UNKNOWN)

MAX_QUESTIONS_PER_ROUND = 3

REQUEST_TEXT_FR = (
    "Demande de précision (démonstration locale, aucun envoi externe). "
    "Merci de répondre aux questions ci-dessous et de joindre, si elle existe, la pièce utile. "
    "La date cible indiquée est une cible de démonstration, pas un délai légal. "
    "Une demande de précision n'est pas une accusation."
)


def deterministic_plan(findings, has_context_claim: bool, answered_ids: set[str]) -> list[str]:
    """Rule-based question selection from unresolved prerequisites (fallback planner)."""
    by_family = {f.family: f for f in findings}
    wanted: list[str] = []
    qty = by_family.get(FindingFamily.QUANTITY)
    if qty and qty.status is FindingStatus.UNRESOLVED:
        wanted += ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]
    elif qty and qty.status is FindingStatus.INSUFFICIENT:
        wanted += ["Q-PROJECT-DATES"]
    cpty = by_family.get(FindingFamily.COUNTERPARTY)
    if cpty and cpty.status is FindingStatus.INSUFFICIENT:
        wanted.append("Q-COUNTERPART-RECORD")
    if not has_context_claim:
        wanted.insert(0, "Q-PURPOSE")
    out = [q for q in dict.fromkeys(wanted) if q not in answered_ids]
    return out[:MAX_QUESTIONS_PER_ROUND]


# Global question-merge policy (one budget for all sources, MAX_QUESTIONS_PER_ROUND in total):
#   1. project-context contradictions needing company confirmation (e.g. Q-HORIZON-CONFIRM);
#   2. questions from the finding-based planner, in the planner's order;
#   3. missing project context (dates, stage, beneficiary);
#   4. supporting reference requests and model-flagged ambiguity (lowest priority).
# Deterministic: tiers are fixed here; no model chooses the ordering. Already answered IDs
# are never asked again.
_CONTEXT_TIER = {
    "DECLARED_HORIZON_DATE_CONFLICT": 1, "DECLARED_HORIZON_TEXT_CONFLICT": 1,
    "INTERPRETED_HORIZON_DATE_CONFLICT": 1, "PURPOSE_CATEGORY_TEXT_CONFLICT": 1,
    "PROJECT_DATES_MISSING": 3, "INVALID_PROJECT_DATE_ORDER": 3,
    "LONG_HORIZON_STAGE_MISSING": 3, "LONG_HORIZON_BENEFICIARY_MISSING": 3,
    "LONG_HORIZON_REFERENCE_MISSING": 4, "CONTEXT_AMBIGUOUS": 4,
}


def merge_question_plan(context_reason_codes, planner_ids, answered_ids) -> list[str]:
    """Combine context and finding-planner questions under one global cap."""
    from boussla.context.questions import QUESTION_ID_BY_REASON

    codes = {str(getattr(code, "value", code)) for code in context_reason_codes}
    tiers: dict[int, list[str]] = {1: [], 2: list(planner_ids), 3: [], 4: []}
    for reason, question_id in QUESTION_ID_BY_REASON.items():  # C's fixed, stable order
        if reason.value in codes:
            tiers[_CONTEXT_TIER[reason.value]].append(question_id)
    answered = set(answered_ids)
    merged = [q for q in dict.fromkeys(tiers[1] + tiers[2] + tiers[3] + tiers[4])
              if q in QUESTIONS and q not in answered]
    return merged[:MAX_QUESTIONS_PER_ROUND]
