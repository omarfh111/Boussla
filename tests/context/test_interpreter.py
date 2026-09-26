import json
from datetime import date

import httpx
import pytest

from boussla.contracts import Mode, PurposeCategory
from boussla.context.interpreter import OpenAIContextInterpreter
from boussla.context.models import ContextInput, HorizonBucket


def context(text="Construction d'un dépôt logistique prévue sur environ dix-huit mois"):
    return ContextInput(
        purpose_category=PurposeCategory.CONSTRUCTION_PROJECT, purpose_text=text,
        planned_start=date(2027, 1, 1), planned_end=date(2028, 6, 30),
        stage=None, beneficiary_type="UNKNOWN", declared_horizon=HorizonBucket.SHORT_HORIZON,
        project_reference="PRIVATE-PROJECT-REF",
    )


def provider_response(*, horizon="LONGER_HORIZON", category="CONSTRUCTION_PROJECT",
                      span="environ dix-huit mois", explicit=None, ambiguities=None):
    data = {
        "suggested_purpose_category": category, "suggested_horizon": horizon,
        "explicit_duration_text": span if explicit is None else explicit,
        "supporting_spans": [span] if span else [], "ambiguities": ambiguities or [],
    }
    return {"status": "completed", "model": "configured-model",
            "output": [{"content": [{"type": "output_text", "text": json.dumps(data)}]}]}


def interpreter(handler):
    return OpenAIContextInterpreter(
        api_key="test-only", model="configured-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def test_long_interpretation_uses_exact_span_and_only_bounded_payload_fields():
    def handler(request):
        payload = json.loads(request.content)
        supplied = json.loads(payload["input"][1]["content"])
        assert set(supplied) == {
            "purpose_text", "declared_purpose_category", "declared_horizon",
            "planned_start", "planned_end", "stage",
        }
        assert "PRIVATE" not in request.content.decode()
        assert "beneficiary_type" not in request.content.decode()
        assert "explicit_duration_text must be copied exactly from purpose_text" in payload["input"][0]["content"]
        return httpx.Response(200, json=provider_response())

    result = interpreter(handler).interpret(context())
    assert result.suggested_purpose_category is PurposeCategory.CONSTRUCTION_PROJECT
    assert result.suggested_horizon is HorizonBucket.LONGER_HORIZON
    assert result.explicit_duration_text == "environ dix-huit mois"
    assert result.supporting_spans == ("environ dix-huit mois",)
    assert result.mode is Mode.LIVE and result.model_id == "configured-model"


def test_short_phrase_can_be_interpreted_without_calculating_days():
    result = interpreter(lambda request: httpx.Response(200, json=provider_response(
        horizon="SHORT_HORIZON", category="OPERATING_USE", span="pendant deux semaines",
    ))).interpret(context("Utilisation courante pendant deux semaines"))
    assert result.suggested_horizon is HorizonBucket.SHORT_HORIZON
    assert result.suggested_purpose_category is PurposeCategory.OPERATING_USE
    assert not hasattr(result, "duration_days")


def test_ambiguous_prose_stays_unknown():
    response = provider_response(horizon="UNKNOWN", category="OTHER_OR_UNKNOWN",
                                 span="", explicit="", ambiguities=["PERIOD_UNCLEAR"])
    result = interpreter(lambda request: httpx.Response(200, json=response)).interpret(context("Projet à préciser"))
    assert result.suggested_horizon is HorizonBucket.UNKNOWN
    assert result.suggested_purpose_category is PurposeCategory.OTHER_OR_UNKNOWN
    assert result.mode is Mode.LIVE and result.ambiguities == ("PERIOD_UNCLEAR",)


@pytest.mark.parametrize("bad", [
    provider_response(span="invented eighteen months"),
    provider_response(explicit="invented duration"),
    provider_response(horizon="LONGER_HORIZON", span="", explicit=""),
    provider_response(horizon="LEGAL_LONG", span="environ dix-huit mois"),
])
def test_fabricated_span_or_invalid_structured_output_degrades_to_unknown(bad):
    result = interpreter(lambda request: httpx.Response(200, json=bad)).interpret(context())
    assert result.suggested_horizon is HorizonBucket.UNKNOWN
    assert result.suggested_purpose_category is PurposeCategory.OTHER_OR_UNKNOWN
    assert result.mode is Mode.TEMPLATE


def test_non_unknown_horizon_without_explicit_duration_span_is_rejected():
    body = provider_response()
    data = json.loads(body["output"][0]["content"][0]["text"])
    data["explicit_duration_text"] = None
    body["output"][0]["content"][0]["text"] = json.dumps(data)
    result = interpreter(lambda request: httpx.Response(200, json=body)).interpret(context())
    assert result.mode is Mode.TEMPLATE and result.suggested_horizon is HorizonBucket.UNKNOWN


def test_exact_explicit_duration_is_added_to_supporting_spans_when_separate():
    body = provider_response()
    data = json.loads(body["output"][0]["content"][0]["text"])
    data["supporting_spans"] = ["Construction d'un dépôt logistique"]
    body["output"][0]["content"][0]["text"] = json.dumps(data)
    result = interpreter(lambda request: httpx.Response(200, json=body)).interpret(context())
    assert result.mode is Mode.LIVE
    assert result.supporting_spans == (
        "Construction d'un dépôt logistique", "environ dix-huit mois",
    )


def test_provider_outage_and_missing_key_are_nonfatal():
    outage = interpreter(lambda request: httpx.Response(503)).interpret(context())
    assert outage.suggested_horizon is HorizonBucket.UNKNOWN and outage.mode is Mode.TEMPLATE
    assert OpenAIContextInterpreter(api_key="", model="configured-model").interpret(context()).mode is Mode.NOT_RUN


def test_oversized_prose_is_not_sent():
    def forbidden(request):
        raise AssertionError("oversized text sent to provider")
    result = interpreter(forbidden).interpret(context("x" * 2001))
    assert result.mode is Mode.NOT_RUN and result.suggested_horizon is HorizonBucket.UNKNOWN


@pytest.mark.parametrize("unsafe_text", [
    "Construction pour matricule fiscal 1234567/A/M/000 sur dix-huit mois",
    "Projet avec facture 500 DT sur dix-huit mois",
    "Travaux pour contact@example.org sur dix-huit mois",
])
def test_obvious_identifiers_or_financial_details_in_prose_are_not_sent(unsafe_text):
    def forbidden(request):
        raise AssertionError("unsafe prose sent to provider")
    result = interpreter(forbidden).interpret(context(unsafe_text))
    assert result.mode is Mode.NOT_RUN and result.suggested_horizon is HorizonBucket.UNKNOWN
