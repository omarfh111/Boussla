"""Live Cloud smoke over public references; prints identifiers and mode only.

Set QDRANT_URL, QDRANT_API_KEY and QDRANT_COLLECTION in the environment first.
This never sends case, taxpayer, invoice or payment content to Qdrant.
"""

from datetime import date
import os
from urllib.parse import urlparse

from boussla.contracts import Audience, FindingFamily, Mode
from boussla.retrieval.corpus import public_reference_retriever
from boussla.retrieval.queries import candidate_passages_for_reasons


def main() -> None:
    retriever = public_reference_retriever()
    if retriever.backend_mode != "QDRANT":
        raise SystemExit(f"Cloud smoke unavailable: {retriever.backend_mode} ({retriever.fallback_reason})")
    print("host", urlparse(os.environ["QDRANT_URL"]).hostname)
    print("collection", retriever.collection)
    print("embedding_model", retriever.model_name, "dimension", retriever.dimension)
    print("point_count", retriever.client.count(retriever.collection, exact=True).count)
    retriever._verify_points()  # all stored payload fields must equal the inspected corpus
    print("payload_match", True)

    reasons = (
        "INVOICE_FIELDS_UNCONFIRMED", "INVOICE_AMOUNT_CONFLICT",
        "INVOICE_LINE_IDENTITY_CONFLICT", "INVOICE_LINE_AMOUNT_CONFLICT",
    )
    for reason in reasons:
        found = candidate_passages_for_reasons(
            retriever, ((FindingFamily.COUNTERPARTY, reason),), as_of=date(2026, 9, 26),
        )
        if not found or any(item.mode is not Mode.LIVE for item in found):
            raise SystemExit(f"Cloud vector query failed: {reason} ({retriever.fallback_reason})")
        print("query", reason, "candidate_ids", ",".join(item.rule_id for item in found))

    company = retriever.search(
        "facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.COMPANY,
    )
    if company:
        raise SystemExit("company audience received references with unknown effective dates")
    print("company_candidates", len(company))

    def unavailable(*args, **kwargs):
        raise RuntimeError("synthetic cloud outage")

    retriever.client.query_points = unavailable
    fallback = retriever.search(
        "facture", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER,
    )
    if not fallback or any(item.mode is not Mode.TEMPLATE for item in fallback):
        raise SystemExit("lexical fallback failed")
    print("fallback_mode", retriever.backend_mode, "candidate_ids", ",".join(item.rule_id for item in fallback))


if __name__ == "__main__":
    main()
