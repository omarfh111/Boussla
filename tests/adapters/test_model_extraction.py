import json

import httpx

from boussla.adapters.model_extraction import OpenAIInvoiceExtractor
from boussla.contracts import DocumentText, Mode, PageText


TEXT = DocumentText(
    document_id="DOC-VARIANT",
    pages=(PageText(page=1, text="Invoice ref: F-77\nBuyer ID: DEMO-MF-BAT"),),
    status="OK",
)


def answer(*, quote="F-77"):
    names = (
        "invoice_number", "issuer_mf_raw", "buyer_mf_raw", "issued_on",
        "currency", "net_millimes", "tax_millimes", "gross_millimes",
    )
    fields = {name: {"raw_value": None, "page": None, "exact_text": None} for name in names}
    fields["invoice_number"] = {"raw_value": "F-77", "page": 1, "exact_text": quote}
    return {"model": "gpt-4.1-mini-2025-04-14", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": json.dumps(fields)}
    ]}]}


def test_model_output_becomes_candidate_only_with_exact_span():
    seen = {}

    def responder(request):
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json=answer())

    client = httpx.Client(transport=httpx.MockTransport(responder))
    proposal = OpenAIInvoiceExtractor(api_key="synthetic-test-key", client=client).extract_fields(TEXT)

    assert seen["payload"]["text"]["format"]["type"] == "json_schema"
    assert proposal.mode is Mode.LIVE
    assert proposal.model_id == "gpt-4.1-mini-2025-04-14"
    assert proposal.candidates[0].raw_value == "F-77"
    assert proposal.candidates[0].evidence_refs[0].exact_text == "F-77"
    assert "buyer_mf_raw" in proposal.missing_fields


def test_hallucinated_quote_routes_to_manual_for_unknown_layout():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=answer(quote="F-999"))))

    proposal = OpenAIInvoiceExtractor(api_key="synthetic-test-key", client=client).extract_fields(TEXT)

    assert proposal.mode is Mode.MANUAL
    assert all(field.raw_value is None for field in proposal.candidates)


def test_missing_key_does_not_call_provider():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(AssertionError("called"))))

    proposal = OpenAIInvoiceExtractor(api_key="", client=client).extract_fields(TEXT)

    assert proposal.mode is Mode.MANUAL


def test_provider_outage_returns_deterministic_baseline():
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    extractor = OpenAIInvoiceExtractor(api_key="synthetic-test-key", client=client)

    actual = extractor.extract_fields(TEXT)
    expected = extractor.baseline.extract_fields(TEXT)

    assert actual == expected
    assert actual.mode is Mode.MANUAL
