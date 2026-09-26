"""Pure assembly of a bounded officer brief; optional model selects IDs only."""

from __future__ import annotations

from typing import Protocol

from boussla.config import get_settings
from boussla.contracts import Audience, FindingFamily, Mode
from boussla.investigator.catalogue import HYPOTHESIS_CATALOGUE
from boussla.investigator.models import (
    EvidenceFeature, HypothesisSupport, InvestigatorBrief, InvestigatorHypothesis,
    InvestigatorInput, InvestigatorResult, Observation, ObservationKind,
)
from boussla.investigator.selector import OpenAIInvestigatorSelector
from boussla.playbook import MAX_QUESTIONS_PER_ROUND, QUESTIONS


class HypothesisSelector(Protocol):
    def select(self, data: InvestigatorInput, eligible_hypotheses: tuple[str, ...],
               eligible_questions: tuple[str, ...]
               ) -> tuple[tuple[str, ...], tuple[str, ...]] | None: ...


_FAMILY_HYPOTHESES = {
    FindingFamily.QUANTITY: ("SECOND_PROJECT_ALLOCATION", "STOCK_REMAINING", "PARTIAL_DELIVERY",
                             "UNIT_OR_ITEM_MAPPING_ISSUE", "MISSING_SUPPORTING_DOCUMENT"),
    FindingFamily.SETTLEMENT: ("PAYMENT_SCHEDULE", "CREDIT_NOTE_OR_REVERSAL",
                               "MISSING_SUPPORTING_DOCUMENT"),
    FindingFamily.COUNTERPARTY: ("SELLER_TRANSCRIPTION_ERROR", "BUYER_TRANSCRIPTION_ERROR",
                                "LATER_INVOICE_CORRECTION", "MISSING_SUPPORTING_DOCUMENT"),
}
_FAMILY_QUESTIONS = {
    FindingFamily.QUANTITY: ("Q-PROJECT-ALLOCATION", "Q-STOCK", "Q-SUPPORTING-DOC"),
    FindingFamily.SETTLEMENT: ("Q-SUPPORTING-DOC",),
    FindingFamily.COUNTERPARTY: ("Q-COUNTERPART-RECORD",),
}
_CONTEXT_QUESTIONS = {
    "DECLARED_HORIZON_DATE_CONFLICT": "Q-HORIZON-CONFIRM",
    "DECLARED_HORIZON_TEXT_CONFLICT": "Q-HORIZON-CONFIRM",
    "PROJECT_DATES_MISSING": "Q-PROJECT-DATES",
    "LONG_HORIZON_STAGE_MISSING": "Q-PROJECT-STAGE",
    "LONG_HORIZON_BENEFICIARY_MISSING": "Q-PROJECT-BENEFICIARY",
    "LONG_HORIZON_REFERENCE_MISSING": "Q-PROJECT-REFERENCE",
}
_LIMITATIONS = (
    "Hypothèses candidates pour examen humain ; aucune accusation ni conclusion juridique.",
    "La sélection du modèle ne modifie ni les constats ni l'indice de revue.",
    "Les scénarios restent hypothétiques jusqu'à acceptation de pièces par le workflow autorisé.",
)


def _support(feature: EvidenceFeature | None) -> HypothesisSupport:
    if feature is None:
        return HypothesisSupport.INSUFFICIENT
    if feature.supporting_refs and feature.contradicting_refs:
        return HypothesisSupport.PLAUSIBLE
    if feature.contradicting_refs:
        return HypothesisSupport.CONTRADICTED
    if feature.supporting_refs:
        return HypothesisSupport.SUPPORTED
    if feature.missing_evidence:
        return HypothesisSupport.INSUFFICIENT
    return HypothesisSupport.WEAK


def _eligible_questions(data: InvestigatorInput) -> tuple[str, ...]:
    wanted: list[str] = []
    if data.context:
        wanted.extend(_CONTEXT_QUESTIONS[code] for code in data.context.reason_codes
                      if code in _CONTEXT_QUESTIONS)
    for finding in data.findings:
        wanted.extend(_FAMILY_QUESTIONS.get(finding.family, ()))
    answered = set(data.clarification.answered_question_ids)
    return tuple(q for q in dict.fromkeys(wanted) if q in QUESTIONS and q not in answered)


def _observations(data: InvestigatorInput) -> tuple[Observation, ...]:
    items: list[Observation] = []
    for finding in data.findings:
        items.append(Observation(ObservationKind.FACT,
                                 f"Constat déterministe {finding.family.value} : {finding.reason_code} "
                                 f"({finding.status.value}).", finding.evidence_refs))
        if finding.evidence_refs:
            items.append(Observation(ObservationKind.FACT,
                                     "Pièces rapprochées pour ce constat : " + ", ".join(finding.evidence_refs),
                                     finding.evidence_refs))
    if data.context:
        items.append(Observation(ObservationKind.DECLARATION,
                                 "Contexte déclaré : " + data.context.declared_purpose_code + ", "
                                 + data.context.declared_horizon_code + "."))
        items.append(Observation(ObservationKind.MODEL_INTERPRETATION,
                                 "Horizon interprété : " + data.context.interpreted_horizon_code +
                                 " ; cohérence calculée : " + data.context.consistency_code + "."))
    if data.clarification.answered_question_ids:
        items.append(Observation(ObservationKind.DECLARATION,
                                 "Réponses enregistrées pour : " +
                                 ", ".join(data.clarification.answered_question_ids) + "."))
    for code in data.history_signal_codes:
        items.append(Observation(ObservationKind.FACT, "Signal historique codé : " + code + "."))
    for scenario in data.scenarios:
        suffix = (" ; indice hypothétique calculé : " + str(scenario.hypothetical_review_index)
                  if scenario.hypothetical_review_index is not None else "")
        items.append(Observation(ObservationKind.HYPOTHETICAL_SCENARIO,
                                 "Scénario " + scenario.scenario_code + " : " + scenario.outcome_code + suffix +
                                 ". Aucune modification du dossier canonique."))
    if data.reference_rule_ids:
        items.append(Observation(ObservationKind.FACT,
                                 "Passages publics candidats à examiner : " +
                                 ", ".join(data.reference_rule_ids) + ".", data.reference_rule_ids))
    return tuple(items[:30])


class InvestigatorAssistant:
    def __init__(self, selector: HypothesisSelector | None = None) -> None:
        self.selector = selector

    def assess(self, data: InvestigatorInput, *, audience: Audience = Audience.OFFICER) -> InvestigatorResult:
        if Audience(audience) is not Audience.OFFICER:
            return InvestigatorResult(None, Mode.NOT_RUN)
        eligible = _eligible_questions(data)
        candidates = tuple(dict.fromkeys(
            hypothesis for finding in data.findings
            for hypothesis in _FAMILY_HYPOTHESES.get(finding.family, ())
        ))
        selected = self.selector.select(data, candidates, eligible) if self.selector and candidates else None
        if selected is None:
            ordered = candidates[:5]
            questions = eligible[:MAX_QUESTIONS_PER_ROUND]
            mode = Mode.TEMPLATE
        else:
            ordered, questions = selected
            # Defensive validation for injected selectors as well as the OpenAI adapter.
            if (len(ordered) > 5 or len(set(ordered)) != len(ordered)
                    or any(h not in candidates or h not in HYPOTHESIS_CATALOGUE for h in ordered)
                    or len(questions) > MAX_QUESTIONS_PER_ROUND
                    or len(set(questions)) != len(questions)
                    or any(q not in eligible or q not in QUESTIONS for q in questions)):
                return InvestigatorAssistant().assess(data, audience=audience)
            mode = Mode.LIVE
        by_id = {feature.hypothesis_id: feature for feature in data.evidence_features}
        hypotheses = tuple(InvestigatorHypothesis(
            hypothesis_id=h, status=_support(by_id.get(h)),
            supporting_refs=by_id[h].supporting_refs if h in by_id else (),
            contradicting_refs=by_id[h].contradicting_refs if h in by_id else (),
            missing_evidence=by_id[h].missing_evidence if h in by_id else (),
            why_it_matters_fr=HYPOTHESIS_CATALOGUE[h],
        ) for h in ordered)
        missing = tuple(dict.fromkeys(
            code for finding in data.findings for code in finding.missing_evidence
        )) + tuple(dict.fromkeys(
            code for feature in data.evidence_features for code in feature.missing_evidence
            if code not in {m for finding in data.findings for m in finding.missing_evidence}
        ))
        observations = _observations(data)
        summary = (
            "Synthèse indicative pour l'agent : "
            f"{len(data.findings)} constat(s) déterministe(s), "
            f"{len(data.history_signal_codes)} signal(aux) historique(s), "
            f"{len(data.clarification.answered_question_ids)} réponse(s), "
            f"{len(hypotheses)} hypothèse(s) candidate(s), "
            f"{len(data.reference_rule_ids)} référence(s) publique(s). "
            "Les détails ci-dessous séparent faits, déclarations, interprétations et scénarios."
        )
        brief = InvestigatorBrief(
            summary_fr=summary, key_observations=observations, top_hypotheses=hypotheses,
            missing_information=missing, suggested_question_ids=tuple(questions),
            what_changed_since_previous_revision=data.history_signal_codes,
            reference_rule_ids=data.reference_rule_ids, limitations=_LIMITATIONS, mode=mode,
        )
        return InvestigatorResult(brief, mode)


def investigator_assistant() -> InvestigatorAssistant:
    settings = get_settings()
    if settings.llm_provider == "openai" and (key := settings.secret("OPENAI_API_KEY")):
        from boussla.adapters.model_extraction import DEFAULT_MODEL
        return InvestigatorAssistant(OpenAIInvestigatorSelector(
            api_key=key, model=settings.openai_chat_model or DEFAULT_MODEL,
            timeout=settings.general_model_timeout_seconds,
        ))
    return InvestigatorAssistant()
