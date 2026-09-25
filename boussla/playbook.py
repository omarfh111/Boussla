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
