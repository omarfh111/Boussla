import json
from datetime import date
from types import SimpleNamespace

import httpx

from boussla.contracts import Audience, FindingFamily, Mode
from boussla.retrieval.corpus import load_public_references
from boussla.retrieval.grounded_rag import OpenAIReferenceNoteGenerator, ReferenceAssistant
from boussla.retrieval.lexical import LexicalReferenceRetriever


REASON = "INVOICE_FIELDS_UNCONFIRMED"
FINDING = SimpleNamespace(family=FindingFamily.COUNTERPARTY, reason_code=REASON,
                          company_id="PRIVATE-COMPANY", transaction_id="PRIVATE-PAYMENT")
AS_OF = date(2026, 9, 26)


def _response(rule_id, *, claim="La facture comporte une date d'opération.", questions=None):
    content = {"claims": [{"text_fr": claim, "rule_ids": [rule_id]}],
               "applicability_questions": questions or ["La version de la source est-elle applicable ?"]}
    return {"status": "completed", "model": "configured-model",
            "output": [{"content": [{"type": "output_text", "text": json.dumps(content)}]}]}


def _generator(handler):
    return OpenAIReferenceNoteGenerator(
        api_key="test-only", model="configured-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _passages():
    retriever = LexicalReferenceRetriever(load_public_references())
    return retriever.search("facture date identification numéro", as_of=AS_OF,
                            jurisdiction="TN", audience=Audience.OFFICER)


def test_generation_receives_only_bounded_reason_and_retrieved_public_passages():
    passages = tuple(_passages())
    def handler(request):
        body = json.loads(request.content)
        supplied = json.loads(body["input"][1]["content"])
        assert set(supplied) == {"findings", "references"}
        assert supplied["findings"] == [{"family": FindingFamily.COUNTERPARTY.value, "reason_code": REASON}]
        assert supplied["references"] == [{"rule_id": p.rule_id, "text": p.text} for p in passages]
        assert "PRIVATE" not in request.content.decode()
        return httpx.Response(200, json=_response(passages[0].rule_id))

    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), _generator(handler)).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.grounded_note and result.grounded_note.candidate_rule_ids == (result.candidate_passages[0].rule_id,)
    assert result.generation_mode is Mode.LIVE and result.retrieval_mode is Mode.TEMPLATE
    assert f"[{result.cited_rule_ids[0]}]" in result.grounded_note.summary_fr


def test_invented_citation_rejects_note_but_preserves_passages():
    generator = _generator(lambda request: httpx.Response(200, json=_response("INVENTED-RULE")))
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), generator).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.candidate_passages and result.grounded_note is None
    assert result.cited_rule_ids == () and result.generation_mode is Mode.NOT_RUN


def test_no_passages_never_calls_generator():
    def forbidden(request):
        raise AssertionError("provider called without public references")
    result = ReferenceAssistant(LexicalReferenceRetriever(()), _generator(forbidden)).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.candidate_passages == () and result.grounded_note is None
    assert result.retrieval_mode is Mode.NOT_RUN


def test_provider_outage_preserves_lexical_passages():
    generator = _generator(lambda request: httpx.Response(503))
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), generator).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.candidate_passages and result.grounded_note is None
    assert result.retrieval_backend == "LEXICAL" and result.generation_mode is Mode.NOT_RUN


def test_company_never_gets_passages_or_officer_note():
    def forbidden(request):
        raise AssertionError("company audience called the provider")
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), _generator(forbidden)).for_findings(
        [FINDING], as_of=AS_OF, audience=Audience.COMPANY,
    )
    assert result.candidate_passages == () and result.grounded_note is None


def test_definitive_applicability_statement_is_rejected():
    rule_id = _passages()[0].rule_id
    generator = _generator(lambda request: httpx.Response(200, json=_response(
        rule_id, claim="Cette règle s'applique au cas."
    )))
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), generator).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.candidate_passages and result.grounded_note is None


def test_rule_id_in_prose_must_also_be_retrieved():
    rule_id = _passages()[0].rule_id
    generator = _generator(lambda request: httpx.Response(200, json=_response(
        rule_id, claim="Voir TN-INVENTED-ARTICLE pour le numéro."
    )))
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), generator).for_findings(
        [FINDING], as_of=AS_OF,
    )
    assert result.candidate_passages and result.grounded_note is None


def test_unmapped_reason_does_not_expose_arbitrary_query_or_call_provider():
    def forbidden(request):
        raise AssertionError("provider called for unmapped finding")
    finding = SimpleNamespace(family=FindingFamily.COUNTERPARTY,
                              reason_code="PRIVATE-COMPANY-QUESTION")
    result = ReferenceAssistant(LexicalReferenceRetriever(load_public_references()), _generator(forbidden)).for_findings(
        [finding], as_of=AS_OF,
    )
    assert result.candidate_passages == () and result.grounded_note is None
