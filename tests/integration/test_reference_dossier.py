"""C-side reference candidates reach the existing officer view and dossier UI."""

from datetime import date

from qdrant_client import QdrantClient

from boussla.contracts import FindingFamily, Mode
from boussla.retrieval.corpus import load_public_references
from boussla.retrieval.grounded_rag import GroundedReferenceNote, ReferenceAssistant
from boussla.retrieval.lexical import LexicalReferenceRetriever
from boussla.retrieval.qdrant_cloud import QdrantReferenceRetriever
from boussla.retrieval.queries import enrich_officer_view
from boussla.services import build_service
from ui import officer as officer_ui


class Embeddings:
    model_name = "TEST_VECTORS_ONLY"
    dimension = 3

    def embed(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]


class CaptureStreamlit:
    def __init__(self):
        self.events = []
        self.session_state = {}

    def __getattr__(self, name):
        if name == "columns":
            return lambda count: (self,) * count
        if name == "radio":
            return lambda *args, **kwargs: "Interne (Agent)"
        if name == "button":
            return lambda *args, **kwargs: False
        return lambda *args, **kwargs: self.events.append((name, args[0] if args else None))


def _officer_case():
    service = build_service()
    actor = service.registry.actors["DEMO-OFFICER"]
    view = service.get_case(actor, "CASE-BRICKS-001")
    finding = view.findings[0].model_copy(update={
        "family": FindingFamily.COUNTERPARTY, "reason_code": "INVOICE_FIELDS_UNCONFIRMED",
    })
    return service, actor, view.model_copy(update={"findings": (finding,)})


def test_qdrant_candidates_reach_officer_view_and_existing_streamlit_dossier(monkeypatch):
    service, actor, view = _officer_case()
    retriever = QdrantReferenceRetriever(
        load_public_references(), url="https://test.cloud.qdrant.io", api_key="test-only",
        collection="public_test", client=QdrantClient(":memory:"), embeddings=Embeddings(),
    )

    enriched = enrich_officer_view(view, retriever, as_of=date(2026, 9, 26))

    assert enriched.candidate_passages
    assert enriched.mode_by_node["retrieval"] is Mode.LIVE
    assert enriched.score == view.score and enriched.findings == view.findings
    capture = CaptureStreamlit()
    monkeypatch.setattr(officer_ui, "st", capture)
    officer_ui.render_dossier(service, actor, enriched)
    assert any(name == "markdown" and "Passages de référence candidats" in value
               for name, value in capture.events)
    assert any(name == "write" and enriched.candidate_passages[0].rule_id in value
               for name, value in capture.events if isinstance(value, str))


def test_lexical_and_missing_corpus_modes_do_not_change_score():
    _, _, view = _officer_case()
    lexical = enrich_officer_view(view, LexicalReferenceRetriever(load_public_references()), as_of=date(2026, 9, 26))
    missing = enrich_officer_view(view, LexicalReferenceRetriever(()), as_of=date(2026, 9, 26))

    assert lexical.candidate_passages and lexical.mode_by_node["retrieval"] is Mode.TEMPLATE
    assert missing.candidate_passages == () and missing.mode_by_node["retrieval"] is Mode.NOT_RUN
    assert lexical.score == missing.score == view.score
    assert lexical.findings == missing.findings == view.findings


def test_cloud_failure_lexical_generation_cannot_change_score_or_findings():
    _, _, view = _officer_case()
    retriever = QdrantReferenceRetriever(
        load_public_references(), url="https://test.cloud.qdrant.io", api_key="test-only",
        collection="public_test", client=QdrantClient(":memory:"), embeddings=Embeddings(),
    )
    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic cloud outage")
    retriever.client.query_points = unavailable

    class StubGenerator:
        def generate(self, reasons, passages):
            assert reasons == ((FindingFamily.COUNTERPARTY, "INVOICE_FIELDS_UNCONFIRMED"),)
            return GroundedReferenceNote(
                summary_fr=f"Référence candidate [{passages[0].rule_id}]",
                candidate_rule_ids=(passages[0].rule_id,), applicability_questions=(),
            )

    original = view.model_dump()
    result = ReferenceAssistant(retriever, StubGenerator()).for_findings(view.findings, as_of=date(2026, 9, 26))

    assert result.retrieval_backend == "LEXICAL" and result.retrieval_mode is Mode.TEMPLATE
    assert result.candidate_passages and result.grounded_note
    assert view.model_dump() == original
    assert view.score == view.model_copy().score and view.findings == view.model_copy().findings
