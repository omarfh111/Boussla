"""Bounded reference queries from check codes; never document or user text."""

from __future__ import annotations

from datetime import date
from typing import Iterable

from boussla.contracts import Audience, FindingFamily, ReferenceRetriever, RetrievedPassage


_QUERY_BY_REASON = {
    (FindingFamily.COUNTERPARTY, "INVOICE_FIELDS_UNCONFIRMED"): "facture date identification numéro",
    (FindingFamily.COUNTERPARTY, "INVOICE_AMOUNT_CONFLICT"): "facture taux montants taxe",
    (FindingFamily.COUNTERPARTY, "INVOICE_LINE_IDENTITY_CONFLICT"): "désignation bien service prix",
    (FindingFamily.COUNTERPARTY, "INVOICE_LINE_AMOUNT_CONFLICT"): "prix hors taxe facture",
}


def query_for_reason(family: FindingFamily, reason_code: str | None) -> str | None:
    """Return a fixed public-reference query only for mapped finding codes."""
    return _QUERY_BY_REASON.get((family, reason_code))


def candidate_passages_for_reasons(
    retriever: ReferenceRetriever,
    reasons: Iterable[tuple[FindingFamily, str | None]],
    *,
    as_of: date,
    audience: Audience = Audience.OFFICER,
    limit: int = 5,
) -> tuple[RetrievedPassage, ...]:
    """Candidate passages for display only; no score or applicability decision."""
    if limit < 1:
        return ()
    found: dict[str, RetrievedPassage] = {}
    for family, reason_code in reasons:
        query = query_for_reason(family, reason_code)
        if query is None:
            continue
        for passage in retriever.search(query, as_of=as_of, jurisdiction="TN", audience=audience, limit=limit):
            found.setdefault(passage.rule_id, passage)
            if len(found) >= limit:
                return tuple(found.values())
    return tuple(found.values())
