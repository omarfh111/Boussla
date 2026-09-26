"""Fixed neutral clarification IDs; Lane A may later add these to its playbook."""

from __future__ import annotations

from collections.abc import Iterable

from boussla.context.consistency import ContextReasonCode


MAX_CONTEXT_QUESTIONS_PER_ROUND = 3

QUESTION_ID_BY_REASON = {
    ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT: "Q-HORIZON-CONFIRM",
    ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT: "Q-HORIZON-CONFIRM",
    ContextReasonCode.INTERPRETED_HORIZON_DATE_CONFLICT: "Q-HORIZON-CONFIRM",
    ContextReasonCode.PURPOSE_CATEGORY_TEXT_CONFLICT: "Q-PURPOSE",
    ContextReasonCode.PROJECT_DATES_MISSING: "Q-PROJECT-DATES",
    ContextReasonCode.INVALID_PROJECT_DATE_ORDER: "Q-PROJECT-DATES",
    ContextReasonCode.LONG_HORIZON_STAGE_MISSING: "Q-PROJECT-STAGE",
    ContextReasonCode.LONG_HORIZON_BENEFICIARY_MISSING: "Q-PROJECT-BENEFICIARY",
    ContextReasonCode.LONG_HORIZON_REFERENCE_MISSING: "Q-PROJECT-REFERENCE",
    ContextReasonCode.CONTEXT_AMBIGUOUS: "Q-PURPOSE",
}

QUESTION_TEXT_FR = {
    "Q-HORIZON-CONFIRM": (
        "La période déclarée et les dates prévues semblent différentes. "
        "Pouvez-vous confirmer la période prévue du projet ?"
    ),
    "Q-PROJECT-DATES": "Quelle est la période d'utilisation prévue (date de début et de fin) pour ce projet ?",
    "Q-PROJECT-STAGE": "À quelle phase du projet cet achat est-il rattaché ?",
    "Q-PROJECT-BENEFICIARY": "Quel projet, lot ou bénéficiaire est concerné par cet achat ?",
    "Q-PROJECT-REFERENCE": (
        "Disposez-vous d'une pièce ou référence décrivant l'affectation prévue de cet achat ?"
    ),
    "Q-PURPOSE": "Pour quel usage cet achat est-il prévu ?",
}


def recommend_question_ids(
    reason_codes: Iterable[ContextReasonCode], *, answered_ids: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return at most three unique IDs in a stable priority order."""
    present = set(reason_codes)
    answered = set(answered_ids)
    out: list[str] = []
    for reason, question_id in QUESTION_ID_BY_REASON.items():
        if reason in present and question_id not in answered and question_id not in out:
            out.append(question_id)
            if len(out) == MAX_CONTEXT_QUESTIONS_PER_ROUND:
                break
    return tuple(out)
