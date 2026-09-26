from dataclasses import replace
from datetime import date

from boussla.contracts import Mode, PurposeCategory
from boussla.context.consistency import (
    ContextConsistencyStatus, ContextReasonCode, evaluate_consistency,
)
from boussla.context.models import ContextInput, ContextInterpretation, HorizonBucket


def long_project():
    return ContextInput(
        purpose_category=PurposeCategory.CONSTRUCTION_PROJECT,
        purpose_text="Construction d'un dépôt logistique prévue sur environ dix-huit mois",
        planned_start=date(2027, 1, 1), planned_end=date(2028, 6, 30),
        stage=None, beneficiary_type="PROJECT", declared_horizon=HorizonBucket.SHORT_HORIZON,
    )


def interpretation(horizon=HorizonBucket.LONGER_HORIZON,
                   category=PurposeCategory.CONSTRUCTION_PROJECT):
    return ContextInterpretation(
        suggested_purpose_category=category, suggested_horizon=horizon,
        explicit_duration_text="environ dix-huit mois" if horizon is not HorizonBucket.UNKNOWN else None,
        supporting_spans=("environ dix-huit mois",) if horizon is not HorizonBucket.UNKNOWN else (),
        ambiguities=(), model_id="synthetic-model", mode=Mode.LIVE,
    )


def test_synthetic_long_project_conflict_and_missing_stage():
    context = long_project()
    result = evaluate_consistency(context, interpretation())
    assert result.duration_days == 546
    assert result.declared_horizon is HorizonBucket.SHORT_HORIZON
    assert result.interpreted_horizon is HorizonBucket.LONGER_HORIZON
    assert result.calculated_horizon is HorizonBucket.LONGER_HORIZON
    assert result.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT in result.reason_codes
    assert ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT in result.reason_codes
    assert ContextReasonCode.LONG_HORIZON_STAGE_MISSING in result.reason_codes
    assert context.declared_horizon is HorizonBucket.SHORT_HORIZON  # no canonical mutation


def test_corrected_declaration_and_complete_long_project_is_consistent():
    context = replace(long_project(), declared_horizon=HorizonBucket.LONGER_HORIZON,
                      stage="FOUNDATION", beneficiary_type="PROJECT", project_reference="P2")
    result = evaluate_consistency(context, interpretation())
    assert result.status is ContextConsistencyStatus.CONSISTENT
    assert result.reason_codes == ()


def test_unknown_declaration_with_agreeing_interpretation_and_dates_is_not_contradiction():
    context = replace(long_project(), declared_horizon=HorizonBucket.UNKNOWN,
                      stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation())
    assert result.status is ContextConsistencyStatus.CONSISTENT
    assert ContextReasonCode.DECLARED_HORIZON_DATE_CONFLICT not in result.reason_codes


def test_short_declaration_and_long_interpretation_without_dates_needs_clarification():
    context = replace(long_project(), planned_start=None, planned_end=None, stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation())
    assert result.calculated_horizon is HorizonBucket.UNKNOWN
    assert result.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert ContextReasonCode.DECLARED_HORIZON_TEXT_CONFLICT in result.reason_codes
    assert ContextReasonCode.PROJECT_DATES_MISSING in result.reason_codes


def test_long_declaration_without_dates_is_insufficient():
    context = replace(long_project(), declared_horizon=HorizonBucket.LONGER_HORIZON,
                      planned_start=None, planned_end=None, stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation())
    assert result.status is ContextConsistencyStatus.INSUFFICIENT
    assert result.duration_days is None
    assert ContextReasonCode.PROJECT_DATES_MISSING in result.reason_codes


def test_semantic_long_but_calculated_short_is_a_clarification_candidate():
    context = replace(long_project(), declared_horizon=HorizonBucket.SHORT_HORIZON,
                      planned_end=date(2027, 3, 1), stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation())
    assert result.calculated_horizon is HorizonBucket.SHORT_HORIZON
    assert result.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert ContextReasonCode.INTERPRETED_HORIZON_DATE_CONFLICT in result.reason_codes


def test_invalid_date_order_is_insufficient_not_negative_finding():
    context = replace(long_project(), planned_end=date(2026, 12, 31), stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation(HorizonBucket.UNKNOWN))
    assert result.status is ContextConsistencyStatus.INSUFFICIENT
    assert result.duration_days is None and result.calculated_horizon is HorizonBucket.UNKNOWN
    assert result.reason_codes == (ContextReasonCode.INVALID_PROJECT_DATE_ORDER,)


def test_category_disagreement_is_neutral_and_does_not_replace_declaration():
    context = replace(long_project(), declared_horizon=HorizonBucket.LONGER_HORIZON, stage="FOUNDATION")
    result = evaluate_consistency(context, interpretation(category=PurposeCategory.RESALE))
    assert ContextReasonCode.PURPOSE_CATEGORY_TEXT_CONFLICT in result.reason_codes
    assert result.status is ContextConsistencyStatus.NEEDS_CLARIFICATION
    assert context.purpose_category is PurposeCategory.CONSTRUCTION_PROJECT


def test_long_project_missing_beneficiary_and_required_reference_only_when_applicable():
    context = replace(long_project(), declared_horizon=HorizonBucket.LONGER_HORIZON,
                      stage="FOUNDATION", beneficiary_type="UNKNOWN", reference_expected=True)
    result = evaluate_consistency(context, interpretation())
    assert ContextReasonCode.LONG_HORIZON_BENEFICIARY_MISSING in result.reason_codes
    assert ContextReasonCode.LONG_HORIZON_REFERENCE_MISSING in result.reason_codes
    complete = evaluate_consistency(replace(context, beneficiary_type="PROJECT", project_reference="P2"),
                                    interpretation())
    assert complete.status is ContextConsistencyStatus.CONSISTENT


def test_provider_outage_does_not_create_context_conflict():
    context = replace(long_project(), declared_horizon=HorizonBucket.LONGER_HORIZON, stage="FOUNDATION")
    unknown = ContextInterpretation(PurposeCategory.OTHER_OR_UNKNOWN, HorizonBucket.UNKNOWN,
                                    None, (), ("MODEL_RESPONSE_UNUSABLE",), None, Mode.TEMPLATE)
    result = evaluate_consistency(context, unknown)
    assert result.status is ContextConsistencyStatus.CONSISTENT
    assert result.reason_codes == ()
