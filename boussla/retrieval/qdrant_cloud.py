"""Cloud Qdrant search over reviewed public references, with local embeddings."""

from __future__ import annotations

from datetime import date
import math
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

from boussla.contracts import Audience, Mode, RetrievedPassage
from boussla.retrieval.lexical import LexicalReferenceRetriever, ReferenceRecord, reference_is_eligible


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
VECTOR_SIZE = 384
MODEL_CACHE = Path(__file__).resolve().parents[2] / "runtime" / "fastembed"
OFFICIAL_HOSTS = frozenset({"www.finances.gov.tn", "finances.gov.tn", "jibaya.tn", "www.jibaya.tn", "www.iort.gov.tn"})


class LocalFastEmbedder:
    model_name = MODEL_NAME
    dimension = VECTOR_SIZE

    def __init__(self) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=MODEL_NAME, cache_dir=str(MODEL_CACHE))

    def embed(self, texts):
        return self.model.embed(texts)


class QdrantReferenceRetriever:
    """Only bounded, reviewed official public excerpts enter the Cloud collection."""

    backend_mode = "QDRANT"
    status = "READY"

    def __init__(
        self, records: tuple[ReferenceRecord, ...], *, url: str, api_key: str,
        collection: str, client=None, embeddings=None,
    ) -> None:
        from qdrant_client import QdrantClient, models

        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
            raise ValueError("Qdrant Cloud HTTPS URL required")
        if parsed.username or parsed.password or not api_key or not collection:
            raise ValueError("Qdrant Cloud configuration incomplete")
        if not 8 <= len(records) <= 50 or len({record.rule_id for record in records}) != len(records):
            raise ValueError("Cloud corpus requires 8–50 unique reviewed references")
        if any(record.review_status != "REVIEWED" or record.jurisdiction != "TN" or
               urlparse(record.source_url).hostname not in OFFICIAL_HOSTS for record in records):
            raise ValueError("only reviewed official Tunisian references may be indexed")

        self.records = records
        self.by_id = {record.rule_id: record for record in records}
        self.collection = collection
        self.embeddings = embeddings if embeddings is not None else LocalFastEmbedder()
        self.dimension = self.embeddings.dimension
        self.model_name = self.embeddings.model_name
        self.client = client if client is not None else QdrantClient(
            url=url, api_key=api_key, prefer_grpc=False, timeout=10, cloud_inference=False,
        )
        self.lexical = LexicalReferenceRetriever(records)
        self.fallback_reason: str | None = None
        self._prepare_collection(models)

    @staticmethod
    def payload_for(record: ReferenceRecord) -> dict:
        return {
            "rule_id": record.rule_id, "source_url": record.source_url,
            "source_hash": record.source_hash, "document_title": record.document_title,
            "source_date": record.source_date.isoformat() if record.source_date else None,
            "page": record.page, "article": record.article, "language": record.language,
            "jurisdiction": record.jurisdiction,
            "effective_from": record.effective_from.isoformat() if record.effective_from else None,
            "effective_to": record.effective_to.isoformat() if record.effective_to else None,
            "review_status": record.review_status, "text": record.text,
        }

    @staticmethod
    def _point_id(rule_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"boussla:public-reference:{rule_id}"))

    def _vectors(self, texts: list[str]) -> list[list[float]]:
        vectors = [[float(value) for value in vector] for vector in self.embeddings.embed(texts)]
        if len(vectors) != len(texts) or any(
            len(vector) != self.dimension or not all(math.isfinite(value) for value in vector)
            for vector in vectors
        ):
            raise ValueError("invalid local embedding result")
        return vectors

    def _verify_points(self) -> None:
        points, next_offset = self.client.scroll(self.collection, limit=len(self.records) + 1, with_payload=True)
        if next_offset is not None or len(points) != len(self.records):
            raise ValueError("unexpected public-reference collection size")
        expected = {self._point_id(record.rule_id): self.payload_for(record) for record in self.records}
        if {str(point.id): point.payload for point in points} != expected:
            raise ValueError("public-reference collection payload mismatch")

    def _prepare_collection(self, models) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=models.VectorParams(size=self.dimension, distance=models.Distance.COSINE),
            )
        count = self.client.count(self.collection, exact=True).count
        if count == len(self.records):
            self._verify_points()
            return
        if count != 0:
            raise ValueError("collection contains unexpected points")
        vectors = self._vectors([record.text for record in self.records])
        self.client.upsert(
            collection_name=self.collection,
            points=[models.PointStruct(
                id=self._point_id(record.rule_id), vector=vector, payload=self.payload_for(record),
            ) for record, vector in zip(self.records, vectors)],
            wait=True,
        )
        if self.client.count(self.collection, exact=True).count != len(self.records):
            raise ValueError("public-reference ingestion incomplete")
        self._verify_points()

    def search(
        self, query: str, *, as_of: date, jurisdiction: str,
        audience: Audience | str, limit: int = 5,
    ) -> list[RetrievedPassage]:
        audience = Audience(audience)
        if not query.strip() or limit < 1 or not any(
            reference_is_eligible(record, as_of=as_of, jurisdiction=jurisdiction, audience=audience)
            for record in self.records
        ):
            return []
        if self.backend_mode == "LEXICAL":
            return self.lexical.search(query, as_of=as_of, jurisdiction=jurisdiction, audience=audience, limit=limit)
        try:
            vector = self._vectors([query])[0]
            response = self.client.query_points(
                collection_name=self.collection, query=vector, limit=len(self.records), with_payload=True,
            )
            found = []
            for point in response.points:
                payload = point.payload or {}
                record = self.by_id.get(payload.get("rule_id"))
                if record is None or str(point.id) != self._point_id(record.rule_id) or payload != self.payload_for(record):
                    raise ValueError("unexpected public-reference result payload")
                if not reference_is_eligible(record, as_of=as_of, jurisdiction=jurisdiction, audience=audience):
                    continue
                if not math.isfinite(point.score):
                    raise ValueError("invalid vector score")
                found.append(RetrievedPassage(
                    rule_id=record.rule_id, source_url=record.source_url,
                    document_title=record.document_title, page=record.page, article=record.article,
                    language=record.language, jurisdiction=record.jurisdiction,
                    review_status=record.review_status, text=record.text,
                    score=str(point.score), mode=Mode.LIVE,
                ))
                if len(found) >= min(limit, 5):
                    break
            return found
        except Exception as exc:  # provider/model failure becomes a labelled lexical fallback
            self.backend_mode = "LEXICAL"
            self.fallback_reason = type(exc).__name__
            return self.lexical.search(query, as_of=as_of, jurisdiction=jurisdiction, audience=audience, limit=limit)
