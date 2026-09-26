"""End-to-end: structured facts -> ChecksEngineV4 -> natural mapped counterparty finding
-> service OfficerCaseView -> bounded reason-code query -> reference assistant ->
candidate passages -> grounded note. Offline: in-memory Qdrant, stub embeddings and a
mocked OpenAI transport, but C's real retriever, generator and citation validation."""
import json
from datetime import date

import httpx
import pytest
from qdrant_client import QdrantClient

from boussla.contracts import Allocation, CompanyCaseView, FindingFamily, FindingStatus, Mode
from boussla.retrieval.corpus import load_public_references
from boussla.retrieval.grounded_rag import OpenAIReferenceNoteGenerator, ReferenceAssistant
from boussla.retrieval.lexical import LexicalReferenceRetriever
from boussla.retrieval.qdrant_cloud import QdrantReferenceRetriever
from boussla.seed import fact_id, load_fixture_facts
from boussla.services import BousslaAppService, build_service

BRICKS = "CASE-BRICKS-001"
CPTY = "CASE-SYN-COUNTERPARTY-001"
FORBIDDEN_IN_PROMPT = ("CASE-", "DEMO-BAT", "DEMO-MF", "Bâtisseur", "Briques Démo", "FAC-DEMO", "4760000",
                       "4800000", "DOC-", "PAY-", "TX-001")


class StubEmbeddings:
    model_name = "TEST_VECTORS_ONLY"
    dimension = 3

    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


def qdrant_retriever():
    return QdrantReferenceRetriever(load_public_references(), url="https://test.cloud.qdrant.io", api_key="test-only",
                                    collection="public_test", client=QdrantClient(":memory:"),
                                    embeddings=StubEmbeddings())


class OpenAIStub:
    """Mocked Responses API: records what the model would receive; answers per mode."""

    def __init__(self, mode="valid"):
        self.mode, self.requests = mode, []

    def __call__(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        if self.mode == "down":
            return httpx.Response(503)
        refs = json.loads(body["input"][1]["content"])["references"]
        rid = refs[0]["rule_id"] if self.mode == "valid" else "TN-INVENTED-99"
        text = {"claims": [{"text_fr": "La facture mentionne le taux et le montant de la taxe.", "rule_ids": [rid]}],
                "applicability_questions": ["Les montants des deux vues portent-ils sur la même base ?"]}
        return httpx.Response(200, json={"status": "completed", "model": "gpt-test",
                                         "output": [{"content": [{"type": "output_text", "text": json.dumps(text)}]}]})


def generator(stub):
    return OpenAIReferenceNoteGenerator(api_key="test-only", model="gpt-test",
                                        client=httpx.Client(transport=httpx.MockTransport(stub)))


def seed_counterparty_case(store):
    """Structured synthetic facts only: the independent seller view carries different totals."""
    facts = load_fixture_facts()
    buyer, seller = facts["invoice_observation"]
    facts["invoice_observation"] = [buyer, seller.model_copy(update={"tax_millimes": 800000, "gross_millimes": 4800000})]
    facts["document"] = [d.model_copy(update={"case_id": CPTY}) for d in facts["document"]]
    with store.write(CPTY) as tx:
        tx.create_case("DEMO-BAT", "seed")
        for kind, rows in facts.items():
            for row in rows:
                tx.put(kind, fact_id(kind, row), row)
        tx.commit_version("Cas synthétique de contrepartie (tests)")


@pytest.fixture
def base():
    svc = build_service()
    seed_counterparty_case(svc.store)
    svc.registry.assign("DEMO-OFFICER", CPTY)
    return svc


def with_assistant(base, assistant):
    return BousslaAppService(base.store, base.registry, settings=base.settings, reference_assistant=assistant)


def officer(svc, case=CPTY):
    return svc.get_case(svc.registry.actors["DEMO-OFFICER"], case)


def deterministic(view):
    return (view.score.review_index, view.score.contributions, view.findings, view.hypotheses, view.scenarios)


def test_natural_finding_flows_to_passages_and_grounded_note(base):
    plain = officer(with_assistant(base, None))
    finding = next(f for f in plain.findings if f.family is FindingFamily.COUNTERPARTY)
    assert (finding.status, finding.reason_code) == (FindingStatus.UNRESOLVED, "INVOICE_AMOUNT_CONFLICT")
    assert plain.candidate_passages == () and plain.reference_note is None

    stub = OpenAIStub("valid")
    view = officer(with_assistant(base, ReferenceAssistant(qdrant_retriever(), generator(stub))))
    assert view.candidate_passages and view.mode_by_node["retrieval"] is Mode.LIVE
    ids = {p.rule_id for p in view.candidate_passages}
    note = view.reference_note
    assert note is not None and set(note.candidate_rule_ids) <= ids and note.generation_mode is Mode.LIVE
    assert note.disclaimer_fr.startswith("Synthèse indicative") and view.mode_by_node["reference_note"] is Mode.LIVE
    assert deterministic(view) == deterministic(plain)  # enrichment after, never into, scoring
    prompt = json.dumps(stub.requests[0], ensure_ascii=False)
    assert json.loads(stub.requests[0]["input"][1]["content"])["findings"] == [
        {"family": "COUNTERPARTY", "reason_code": "INVOICE_AMOUNT_CONFLICT"}]
    assert not [t for t in FORBIDDEN_IN_PROMPT if t in prompt]


def test_company_never_receives_passages_or_note(base):
    calls = []

    class Spy(ReferenceAssistant):
        def for_findings(self, *a, **k):
            calls.append(k.get("audience"))
            return super().for_findings(*a, **k)
    svc = with_assistant(base, Spy(qdrant_retriever(), generator(OpenAIStub())))
    company = svc.get_case(svc.registry.actors["DEMO-COMPANY-BAT"], CPTY)
    assert isinstance(company, CompanyCaseView) and calls == []
    assert "candidate_passages" not in CompanyCaseView.model_fields and "reference_note" not in CompanyCaseView.model_fields
    assert "TN-" not in company.model_dump_json()


def test_invented_citation_yields_no_note_but_keeps_passages(base):
    view = officer(with_assistant(base, ReferenceAssistant(qdrant_retriever(), generator(OpenAIStub("invented")))))
    assert view.candidate_passages and view.reference_note is None
    assert view.mode_by_node["reference_note"] is Mode.NOT_RUN


def test_generation_failure_keeps_passages_and_score(base):
    plain = officer(with_assistant(base, None))
    view = officer(with_assistant(base, ReferenceAssistant(qdrant_retriever(), generator(OpenAIStub("down")))))
    assert view.candidate_passages and view.reference_note is None
    assert deterministic(view) == deterministic(plain)


def test_cloud_failure_degrades_to_lexical_template(base):
    retriever = qdrant_retriever()

    def outage(*a, **k):
        raise RuntimeError("synthetic cloud outage")
    retriever.client.query_points = outage
    view = officer(with_assistant(base, ReferenceAssistant(retriever, None)))
    assert view.candidate_passages and view.mode_by_node["retrieval"] is Mode.TEMPLATE
    assert all(p.mode is Mode.TEMPLATE for p in view.candidate_passages)


def test_modes_lexical_and_not_run(base):
    lexical = officer(with_assistant(base, ReferenceAssistant(LexicalReferenceRetriever(load_public_references()))))
    empty = officer(with_assistant(base, ReferenceAssistant(LexicalReferenceRetriever(()))))
    none = officer(with_assistant(base, None))
    assert lexical.mode_by_node["retrieval"] is Mode.TEMPLATE and lexical.candidate_passages
    assert empty.mode_by_node["retrieval"] is Mode.NOT_RUN and empty.candidate_passages == ()
    assert none.mode_by_node["retrieval"] is Mode.NOT_RUN
    assert deterministic(lexical) == deterministic(empty) == deterministic(none)


def test_assistant_exception_is_contained(base):
    class Broken:
        retriever = None

        def for_findings(self, *a, **k):
            raise RuntimeError("boom")
    plain = officer(with_assistant(base, None))
    view = officer(with_assistant(base, Broken()))
    assert view.mode_by_node["retrieval"] is Mode.ERROR and view.candidate_passages == ()
    assert deterministic(view) == deterministic(plain)


def test_brick_quantity_case_is_not_forced_into_references(base):
    seen = []

    class Spy(ReferenceAssistant):
        def for_findings(self, findings, **k):
            seen.append(k["as_of"])
            return super().for_findings(findings, **k)
    svc = with_assistant(base, Spy(qdrant_retriever(), generator(OpenAIStub())))
    view = officer(svc, BRICKS)
    assert view.score.review_index == 40 and view.candidate_passages == () and view.reference_note is None
    assert seen == [view.score.cutoff.date()]  # trusted server-side cutoff, not user input


def test_enrichment_is_cached_per_version_and_40_to_0_unchanged(base):
    stub = OpenAIStub("valid")
    svc = with_assistant(base, ReferenceAssistant(qdrant_retriever(), generator(stub)))
    for _ in range(3):
        officer(svc)
    assert len(stub.requests) == 1  # reruns reuse the per-version result
    co, off = svc.registry.actors["DEMO-COMPANY-BAT"], svc.registry.actors["DEMO-OFFICER"]
    v = lambda: svc.store.case_meta(BRICKS)["version"]  # noqa: E731
    d = svc.prepare_clarification(off, BRICKS, v())
    req = svc.publish_clarification(off, BRICKS, d.draft_id, v(), "p")
    from boussla.config import FIXTURE_ROOT
    doc = svc.upload_document(co, BRICKS, (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes(),
                              "a.pdf", "application/pdf", v(), "u")
    resp = svc.submit_response(co, BRICKS, req.request.request_id, {
        "document_ids": [doc.document.document_id],
        "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001", "splits": {"P1": "1000", "P2": "1000"}}}, v(), "r")
    before = v()
    result = svc.accept_evidence(off, BRICKS, resp.proposal_ids[0], before, "a")
    assert (result.score_before.review_index, result.score_after.review_index) == (40, 0)
    assert [a.quantity for a in svc.store.facts(BRICKS, "allocation", Allocation, version=before)] == ["2000"]


def test_build_service_wires_assistant_hermetically():
    svc = build_service()  # hermetic env: no Qdrant/OpenAI credentials
    assert svc.reference_assistant is not None and svc.reference_assistant.generator is None
    assert svc.reference_assistant.retriever.backend_mode == "LEXICAL"
    assert officer(svc, BRICKS).mode_by_node["retrieval"] is Mode.TEMPLATE
