from dataclasses import replace
from datetime import date

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import pytest

from boussla.contracts import Audience, FindingFamily, Mode
from boussla.retrieval.corpus import load_public_references, public_reference_retriever
from boussla.retrieval.qdrant_cloud import QdrantReferenceRetriever
from boussla.retrieval.queries import candidate_passages_for_reasons


class StubEmbeddings:
    model_name = "TEST_VECTORS_ONLY"
    dimension = 3

    def __init__(self):
        self.inputs = []

    def embed(self, texts):
        self.inputs.extend(texts)
        return [[1.0, 0.0, 0.0] if "facture" in text.lower() else [0.0, 1.0, 0.0]
                for text in texts]


def test_qdrant_client_collection_ingestion_payload_and_bounded_query():
    records = load_public_references()
    embeddings = StubEmbeddings()
    client = QdrantClient(":memory:")  # isolated test transport; production uses Cloud URL
    retriever = QdrantReferenceRetriever(
        records, url="https://test.cloud.qdrant.io", api_key="test-only", collection="public_test",
        client=client, embeddings=embeddings,
    )

    assert retriever.backend_mode == "QDRANT"
    assert client.collection_exists("public_test")
    assert client.count("public_test", exact=True).count == len(records)
    assert len(embeddings.inputs) == len(records)
    points, _ = client.scroll("public_test", limit=len(records), with_payload=True)
    by_id = {record.rule_id: record for record in records}
    for point in points:
        source = by_id[point.payload["rule_id"]]
        assert point.payload == retriever.payload_for(source)

    found = candidate_passages_for_reasons(
        retriever, ((FindingFamily.COUNTERPARTY, "INVOICE_FIELDS_UNCONFIRMED"),),
        as_of=date(2026, 9, 26),
    )
    assert found and found[0].mode is Mode.LIVE
    assert len(embeddings.inputs) == len(records) + 1  # one bounded query vector generated locally
    assert all(item.source_url in {record.source_url for record in records} for item in found)
    assert retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="FR", audience=Audience.OFFICER) == []
    assert retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.COMPANY) == []


def test_query_failure_switches_explicitly_to_lexical():
    records = load_public_references()
    client = QdrantClient(":memory:")
    retriever = QdrantReferenceRetriever(
        records, url="https://test.cloud.qdrant.io", api_key="test-only", collection="public_test",
        client=client, embeddings=StubEmbeddings(),
    )
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic cloud outage")
    client.query_points = fail

    found = retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER)

    assert found and all(item.mode is Mode.TEMPLATE for item in found)
    assert retriever.backend_mode == "LEXICAL"
    assert retriever.fallback_reason == "RuntimeError"


def test_qdrant_postfilter_respects_effective_interval_and_audience():
    records = list(load_public_references())
    future_id = records[0].rule_id
    expired_id = records[1].rule_id
    records[0] = replace(records[0], effective_from=date(2027, 1, 1))
    records[1] = replace(records[1], effective_from=date(2025, 1, 1), effective_to=date(2025, 12, 31))
    retriever = QdrantReferenceRetriever(
        tuple(records), url="https://test.cloud.qdrant.io", api_key="test-only",
        collection="public_test", client=QdrantClient(":memory:"), embeddings=StubEmbeddings(),
    )

    officer = retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER, limit=8)
    company = retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.COMPANY, limit=8)

    assert future_id not in {item.rule_id for item in officer}
    assert expired_id not in {item.rule_id for item in officer}
    assert company == []


def test_missing_local_model_falls_back_to_lexical(monkeypatch):
    from boussla.retrieval import qdrant_cloud

    def unavailable():
        raise OSError("synthetic model unavailable")
    monkeypatch.setattr(qdrant_cloud, "LocalFastEmbedder", unavailable)

    retriever = public_reference_retriever(
        qdrant_url="https://test.cloud.qdrant.io", api_key="test-only", collection="model_failure_test",
    )

    assert retriever.backend_mode == "LEXICAL"
    assert retriever.fallback_reason == "OSError"
    assert retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER)


def test_factory_missing_corpus_is_not_supplied(tmp_path):
    retriever = public_reference_retriever(tmp_path / "missing.json", qdrant_url="", api_key="")

    assert retriever.backend_mode == "NOT_SUPPLIED"
    assert retriever.search("facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER) == []


def test_factory_without_cloud_credentials_is_labelled_lexical():
    retriever = public_reference_retriever(qdrant_url="", api_key="")

    assert retriever.backend_mode == "LEXICAL"
    assert retriever.fallback_reason == "QDRANT_NOT_CONFIGURED"


def test_existing_collection_rejects_foreign_point_without_deleting_it():
    records = load_public_references()
    client = QdrantClient(":memory:")
    settings = dict(url="https://test.cloud.qdrant.io", api_key="test-only",
                    collection="public_test", client=client, embeddings=StubEmbeddings())
    QdrantReferenceRetriever(records, **settings)
    client.upsert("public_test", points=[PointStruct(
        id="818f7d8e-9e62-48dc-9f18-a4f56ca2ee50", vector=[1.0, 0.0, 0.0],
        payload={"rule_id": "FOREIGN"},
    )])

    with pytest.raises(ValueError, match="unexpected points"):
        QdrantReferenceRetriever(records, **settings)
    assert client.count("public_test", exact=True).count == len(records) + 1
