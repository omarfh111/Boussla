from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from boussla.contracts import PurposeCategory
from boussla.context.duration import DEMO_SHORT_HORIZON_MAX_DAYS, calculate_duration_days, classify_horizon
from boussla.context.models import ContextInput, HorizonBucket


@pytest.mark.parametrize("days,bucket", [
    (0, HorizonBucket.SHORT_HORIZON), (1, HorizonBucket.SHORT_HORIZON),
    (89, HorizonBucket.SHORT_HORIZON), (90, HorizonBucket.SHORT_HORIZON),
    (91, HorizonBucket.LONGER_HORIZON), (365, HorizonBucket.LONGER_HORIZON),
    (546, HorizonBucket.LONGER_HORIZON),
])
def test_duration_boundary_is_pure_calendar_difference(days, bucket):
    start = date(2027, 1, 1)
    assert calculate_duration_days(start, start + timedelta(days=days)) == days
    assert classify_horizon(days) is bucket
    assert DEMO_SHORT_HORIZON_MAX_DAYS == 90


def test_missing_dates_are_unknown():
    start = date(2027, 1, 1)
    assert calculate_duration_days(None, start) is None
    assert calculate_duration_days(start, None) is None
    assert classify_horizon(None) is HorizonBucket.UNKNOWN


def test_end_before_start_is_explicitly_invalid():
    with pytest.raises(ValueError, match="before"):
        calculate_duration_days(date(2027, 1, 2), date(2027, 1, 1))
    with pytest.raises(ValueError):
        classify_horizon(-1)


def test_narrow_input_from_context_claim_excludes_company_and_financial_fields():
    claim = SimpleNamespace(
        purpose_category=PurposeCategory.CONSTRUCTION_PROJECT,
        purpose_text="Construction d'un dépôt sur dix-huit mois",
        planned_start=date(2027, 1, 1), planned_end=date(2028, 6, 30),
        stage=None, beneficiary_type="UNKNOWN", company_id="PRIVATE-COMPANY",
        tax_id="PRIVATE-TAX", invoice_amount="PRIVATE-AMOUNT",
    )
    context = ContextInput.from_claim(claim, declared_horizon=HorizonBucket.SHORT_HORIZON)
    assert context.purpose_category is PurposeCategory.CONSTRUCTION_PROJECT
    assert context.declared_horizon is HorizonBucket.SHORT_HORIZON
    assert context.planned_end == date(2028, 6, 30)
    assert "PRIVATE" not in repr(context)
    assert not hasattr(context, "company_id")
