"""Labelled lexical fallback over caller-supplied inspected public passages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Iterable

from boussla.contracts import Audience, Mode, RetrievedPassage


@dataclass(frozen=True)
class ReferenceRecord:
    rule_id: str
    source_url: str
    source_hash: str
    document_title: str
    source_date: date | None
    page: int | None
    article: str | None
    language: str
    jurisdiction: str
    effective_from: date | None
    effective_to: date | None
    review_status: str
    text: str

    def __post_init__(self) -> None:
        if (
            not self.rule_id or not self.text.strip() or not self.source_url.startswith("https://")
            or not re.fullmatch(r"[0-9a-fA-F]{64}", self.source_hash)
        ):
            raise ValueError("reference needs source URL, hash, ID and inspected text")


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"\w+", value.casefold()))


class LexicalReferenceRetriever:
    """Searches public references only; no company or financial index exists here."""

    def __init__(self, records: Iterable[ReferenceRecord]) -> None:
        self.records = tuple(records)
        if len({item.rule_id for item in self.records}) != len(self.records):
            raise ValueError("duplicate reference ID")
        self.status = "READY" if self.records else "NOT_SUPPLIED"
        self.backend_mode = "LEXICAL" if self.records else "NOT_SUPPLIED"
        self.fallback_reason: str | None = None

    def search(
        self, query: str, *, as_of: date, jurisdiction: str,
        audience: Audience | str, limit: int = 5,
    ) -> list[RetrievedPassage]:
        audience = Audience(audience)
        terms = _tokens(query)
        if not terms or limit < 1:
            return []
        ranked: list[tuple[int, ReferenceRecord]] = []
        for item in self.records:
            if not reference_is_eligible(item, as_of=as_of, jurisdiction=jurisdiction, audience=audience):
                continue
            overlap = len(terms & _tokens(item.text))
            if overlap:
                ranked.append((overlap, item))
        ranked.sort(key=lambda pair: (-pair[0], pair[1].rule_id))
        return [
            RetrievedPassage(
                rule_id=item.rule_id, source_url=item.source_url,
                document_title=item.document_title, page=item.page, article=item.article,
                language=item.language, jurisdiction=item.jurisdiction,
                review_status=item.review_status, text=item.text,
                score=str(overlap), mode=Mode.TEMPLATE,
            )
            for overlap, item in ranked[:min(limit, 5)]
        ]


def reference_is_eligible(item: ReferenceRecord, *, as_of: date, jurisdiction: str, audience: Audience) -> bool:
    """Shared post-retrieval applicability bounds; relevance is never a legal decision."""
    if item.jurisdiction != jurisdiction:
        return False
    if item.effective_from and as_of < item.effective_from:
        return False
    if item.effective_to and as_of > item.effective_to:
        return False
    if audience is Audience.COMPANY and (item.review_status != "REVIEWED" or item.effective_from is None):
        return False
    return True
