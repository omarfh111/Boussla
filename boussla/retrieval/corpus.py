"""Load a small, inspected public-reference corpus for officer candidates."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from urllib.parse import urlparse

from boussla.retrieval.lexical import LexicalReferenceRetriever, ReferenceRecord


DEFAULT_CORPUS = Path(__file__).with_name("public_references.json")
OFFICIAL_HOSTS = frozenset({"www.finances.gov.tn", "finances.gov.tn", "jibaya.tn", "www.jibaya.tn", "www.iort.gov.tn"})
FIELDS = frozenset(ReferenceRecord.__dataclass_fields__)


def load_public_references(path: str | Path = DEFAULT_CORPUS) -> tuple[ReferenceRecord, ...]:
    """Reject malformed provenance; a missing corpus is explicitly unsupplied."""
    path = Path(path)
    if not path.exists():
        return ()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or len(data) > 15:
            raise ValueError("public corpus must be a list of at most 15 records")
        records = []
        for item in data:
            if not isinstance(item, dict) or set(item) != FIELDS:
                raise ValueError("public reference metadata is incomplete")
            url = urlparse(item["source_url"])
            if url.scheme != "https" or url.hostname not in OFFICIAL_HOSTS or url.username or url.password:
                raise ValueError("public reference source is not allowlisted")
            if item["jurisdiction"] != "TN" or item["review_status"] not in {"REVIEWED", "UNREVIEWED"}:
                raise ValueError("invalid jurisdiction or review status")
            if item["language"] not in {"fr", "ar"}:
                raise ValueError("unsupported public reference language")
            for field in ("source_date", "effective_from", "effective_to"):
                item[field] = date.fromisoformat(item[field]) if item[field] is not None else None
            if item["effective_from"] and item["effective_to"] and item["effective_from"] > item["effective_to"]:
                raise ValueError("invalid effective interval")
            records.append(ReferenceRecord(**item))
        return tuple(records)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, KeyError) as exc:
        raise ValueError("public reference corpus is unreadable or malformed") from exc


def public_reference_retriever(path: str | Path = DEFAULT_CORPUS) -> LexicalReferenceRetriever:
    return LexicalReferenceRetriever(load_public_references(path))
