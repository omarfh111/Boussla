from dataclasses import replace
from datetime import date

from boussla.contracts import Mode, PurposeCategory
from boussla.context.assistant import ContextConsistencyAssistant
from boussla.context.consistency import ContextConsistencyStatus, ContextReasonCode
from boussla.context.interpreter import OpenAIContextInterpreter
from boussla.context.models import ContextInput, ContextInterpretation, HorizonBucket
from boussla.context.questions import (
    MAX_CONTEXT_QUESTIONS_PER_ROUND, QUESTION_ID_BY_REASON, QUESTION_TEXT_FR, recommend_question_ids,
)


def project():
    return ContextInput(
        purpose_category=PurposeCategory.CONSTRUCTION_PROJECT,
        purpose_text="Construction d'un dépôt logistique prévue sur environ dix-huit mois",
        planned_start=date(2027, 1, 1), planned_end=date(2028, 6, 30),
        stage=None, beneficiary_type="PROJECT", declared_horizon=HorizonBucket.SHORT_HORIZON,
    )


class LongInterpreter:
    def interpret(self, context):
        return ContextInterpretation(
            PurposeCategory.CONSTRUCTION_PROJECT, HorizonBucket.LONGER_HORIZON,
            "environ dix-huit mois", ("environ dix-huit mois",), (), "synthetic-model", Mode.LIVE,
        )


def test_fixture_assessment_recommends_horizon_confirmation_and_stage():
    original = project()
    assessment = ContextConsistencyAssistant(LongInterpreter()).assess(original)
    assert assessment.duration_days == 546
    assert assessment.calculated_horizon is HorizonBucket.LONGER_HORIZON
    assert assessment.consistency.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert assessment.recommended_question_ids == ("Q-HORIZON-CONFIRM", "Q-PROJECT-STAGE")
    assert assessment.mode is Mode.LIVE
    assert original.declared_horizon is HorizonBucket.SHORT_HORIZON
    assert not hasattr(assessment, "review_index") and not hasattr(assessment, "findings")


def test_complete_longer_project_does_not_trigger_repeated_questions():
    complete = replace(project(), declared_horizon=HorizonBucket.LONGER_HORIZON,
                       stage="FOUNDATION", beneficiary_type="PROJECT", project_reference="P2")
    assessment = ContextConsistencyAssistant(LongInterpreter()).assess(complete)
    assert assessment.consistency.status is ContextConsistencyStatus.CONSISTENT
    assert assessment.recommended_question_ids == ()


def test_recommendations_are_deduplicated_capped_and_skip_answered_ids():
    reasons = (
        ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT,
        ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT,
        ContextReasonCode.PROJECT_DATES_MISSING,
        ContextReasonCode.LONG_HORIZON_STAGE_MISSING,
        ContextReasonCode.LONG_HORIZON_BENEFICIARY_MISSING,
        ContextReasonCode.LONG_HORIZON_REFERENCE_MISSING,
    )
    assert recommend_question_ids(reasons) == (
        "Q-HORIZON-CONFIRM", "Q-PROJECT-DATES", "Q-PROJECT-STAGE",
    )
    assert recommend_question_ids(reasons, answered_ids={"Q-HORIZON-CONFIRM", "Q-PROJECT-DATES"}) == (
        "Q-PROJECT-STAGE", "Q-PROJECT-BENEFICIARY", "Q-PROJECT-REFERENCE",
    )
    assert MAX_CONTEXT_QUESTIONS_PER_ROUND == 3


def test_all_recommended_ids_have_fixed_french_text_and_no_accusation():
    ids = set(QUESTION_ID_BY_REASON.values())
    assert all(qid in QUESTION_TEXT_FR for qid in ids)
    assert all("fraude" not in QUESTION_TEXT_FR[qid].lower() for qid in ids)


def test_provider_disabled_keeps_date_consistency_and_questions():
    assistant = ContextConsistencyAssistant(OpenAIContextInterpreter(api_key=None))
    assessment = assistant.assess(project())
    assert assessment.interpretation.mode is Mode.NOT_RUN
    assert assessment.interpretation.suggested_horizon is HorizonBucket.UNKNOWN
    assert assessment.duration_days == 546
    assert assessment.consistency.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT in assessment.reason_codes
    assert "Q-HORIZON-CONFIRM" in assessment.recommended_question_ids


def test_answered_question_is_not_repeated_in_assessment():
    assessment = ContextConsistencyAssistant(LongInterpreter()).assess(
        project(), answered_question_ids={"Q-HORIZON-CONFIRM"},
    )
    assert assessment.recommended_question_ids == ("Q-PROJECT-STAGE",)
