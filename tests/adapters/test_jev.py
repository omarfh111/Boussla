import httpx

from boussla.adapters.jev import CRITERIA, JevDocumentRouter
from boussla.contracts import DocumentClass, Mode


def test_missing_key_returns_explicit_manual_unknown():
    result = JevDocumentRouter(api_key="").classify("DOC-1", "Facture", ("INVOICE",))

    assert result.candidate_class is DocumentClass.OTHER_OR_UNKNOWN
    assert result.mode is Mode.MANUAL
    assert result.model_id is None


def test_choice_response_records_actual_model_and_uncertainty():
    seen = {}

    def responder(request):
        seen["url"] = str(request.url)
        seen["payload"] = __import__("json").loads(request.content)
        return httpx.Response(200, json={
            "model": "jev-1.13.0", "answers": {"document_type": {
                "type": "choice", "choice": "INVOICE", "confidence": 0.9,
                "probabilities": {key: (0.9 if key == "INVOICE" else 0.1 if key == "OTHER_OR_UNKNOWN" else 0.0) for key in CRITERIA},
            }}, "usage": {"input_tokens": 42, "output_tokens": 5},
        })

    client = httpx.Client(transport=httpx.MockTransport(responder))
    result = JevDocumentRouter(api_key="synthetic-test-key", client=client).classify(
        "DOC-1", "Facture fictive", ("INVOICE", "OTHER_OR_UNKNOWN")
    )

    assert seen["url"] == "https://api.typesafe.ai/v1/systemone"
    assert seen["payload"]["model"] == "jev-1.13.0"
    assert seen["payload"]["questions"]["document_type"]["type"] == "choice"
    assert result.candidate_class is DocumentClass.INVOICE
    assert result.model_id == "jev-1.13.0"
    assert result.uncertainty == "0.1"
    assert result.mode is Mode.LIVE


def test_provider_error_and_invalid_answer_fall_back_to_manual():
    for response in (
        httpx.Response(401),
        httpx.Response(429),
        httpx.Response(529),
        # NaN confidence sent as raw JSON: httpx refuses to serialize float("nan") itself.
        httpx.Response(200, headers={"content-type": "application/json"}, content=(
            b'{"model": "jev-1.13.0", "answers": {"document_type": '
            b'{"type": "choice", "choice": "INVOICE", "confidence": NaN}}}')),
    ):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: response))
        result = JevDocumentRouter(api_key="synthetic-test-key", client=client).classify(
            "DOC-1", "Facture fictive", ("INVOICE", "OTHER_OR_UNKNOWN")
        )
        assert result.candidate_class is DocumentClass.OTHER_OR_UNKNOWN
        assert result.mode is Mode.MANUAL


def test_ambiguous_or_too_long_text_is_not_sent():
    def no_request(request):
        raise AssertionError("request must not be sent")

    client = httpx.Client(transport=httpx.MockTransport(no_request))
    router = JevDocumentRouter(api_key="synthetic-test-key", client=client, max_chars=20)

    assert router.classify("DOC-1", "x" * 21, ("INVOICE",)).mode is Mode.MANUAL
    assert router.classify("DOC-1", "", ("INVOICE",)).mode is Mode.MANUAL
