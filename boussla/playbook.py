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
    Question(question_id="Q-PAYMENT-DETAILS", answer_kind="TEXT_WITH_FILE",
             text_fr="Pouvez-vous expliquer le règlement de cette opération et joindre un justificatif si disponible ?"),
    Question(question_id="Q-PAYMENT-AMOUNT", answer_kind="NUMBER",
             text_fr="Quel montant a été réglé, dans la devise de la facture ?"),
    Question(question_id="Q-PAYMENT-DATE", answer_kind="DATE",
             text_fr="À quelle date le règlement a-t-il été effectué ?"),
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

AUTO_REQUEST_TEXT_FR = (
    "Demande de précision générée automatiquement à partir d'un catalogue fixe de questions "
    "(démonstration locale, aucun envoi externe). Elle sert uniquement à compléter les informations "
    "du dossier : ce n'est ni une accusation ni une décision. Merci de répondre aux questions ci-dessous "
    "et de joindre, si elle existe, la pièce utile. La date cible indiquée est une cible de démonstration, "
    "pas un délai légal."
)


def deterministic_plan(findings, has_context_claim: bool, answered_ids: set[str]) -> list[str]:
    """Rule-based question selection from unresolved prerequisites (fallback planner)."""
    # One explained transaction must not hide an unresolved transaction of the same family.
    by_family = {}
    rank = {FindingStatus.UNRESOLVED: 2, FindingStatus.INSUFFICIENT: 1}
    for finding in findings:
        prior = by_family.get(finding.family)
        if prior is None or rank.get(finding.status, 0) > rank.get(prior.status, 0):
            by_family[finding.family] = finding
    wanted: list[str] = []
    qty = by_family.get(FindingFamily.QUANTITY)
    if qty and qty.status is FindingStatus.UNRESOLVED:
        wanted += ["Q-PROJECT-ALLOCATION", "Q-SUPPORTING-DOC", "Q-STOCK"]
    elif qty and qty.status is FindingStatus.INSUFFICIENT:
        wanted += ["Q-PROJECT-DATES"]
    cpty = by_family.get(FindingFamily.COUNTERPARTY)
    if cpty and cpty.status in (FindingStatus.INSUFFICIENT, FindingStatus.UNRESOLVED):
        wanted.append("Q-COUNTERPART-RECORD")
    settlement = by_family.get(FindingFamily.SETTLEMENT)
    if settlement and settlement.status is FindingStatus.UNRESOLVED:
        wanted += ["Q-PAYMENT-DETAILS", "Q-PAYMENT-AMOUNT", "Q-PAYMENT-DATE"]
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


QUESTION_FAMILY = {
    "Q-PROJECT-ALLOCATION": FindingFamily.QUANTITY, "Q-SUPPORTING-DOC": FindingFamily.QUANTITY,
    "Q-STOCK": FindingFamily.QUANTITY, "Q-COUNTERPART-RECORD": FindingFamily.COUNTERPARTY,
    "Q-PAYMENT-DETAILS": FindingFamily.SETTLEMENT, "Q-PAYMENT-AMOUNT": FindingFamily.SETTLEMENT,
    "Q-PAYMENT-DATE": FindingFamily.SETTLEMENT,
}


def scoped_questions(question_ids, findings, requests=()):
    result = []
    for qid in question_ids:
        question = QUESTIONS[qid]
        family = QUESTION_FAMILY.get(qid)
        candidates = sorted({f.transaction_id for f in findings if f.family == family
                             and f.status in (FindingStatus.UNRESOLVED, FindingStatus.INSUFFICIENT)})
        already = {tx for request in requests for q in request.questions if q.question_id == qid
                   for tx in q.related_fact_ids}
        remaining = [tx for tx in candidates if tx not in already]
        if family and not remaining:
            continue
        related = tuple(remaining[:1])
        result.append(question.model_copy(update={"related_fact_ids": related,
            "scope_note_fr": "Opération concernée : " + related[0] if related else None}))
    return tuple(result)


def fully_asked_questions(findings, requests):
    result = set()
    for qid in QUESTIONS:
        asked = [q for request in requests for q in request.questions if q.question_id == qid]
        if not asked:
            continue
        family = QUESTION_FAMILY.get(qid)
        candidates = {f.transaction_id for f in findings if f.family == family
                      and f.status in (FindingStatus.UNRESOLVED, FindingStatus.INSUFFICIENT)}
        covered = {tx for q in asked for tx in q.related_fact_ids}
        if not family or any(not q.related_fact_ids for q in asked) or candidates <= covered:
            result.add(qid)
    return result
