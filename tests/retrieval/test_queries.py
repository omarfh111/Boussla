from datetime import date

from boussla.contracts import Audience, FindingFamily
from boussla.retrieval.corpus import public_reference_retriever
from boussla.retrieval.queries import candidate_passages_for_reasons, query_for_reason


def test_known_reason_generates_only_bounded_static_terms():
    query = query_for_reason(FindingFamily.COUNTERPARTY, "INVOICE_FIELDS_UNCONFIRMED")

    assert query == "facture date identification numéro"
    assert query_for_reason(FindingFamily.QUANTITY, "INVOICE_FIELDS_UNCONFIRMED") is None
    assert query_for_reason(FindingFamily.COUNTERPARTY, "unknown DEMO-MF-BAT") is None


def test_candidate_search_deduplicates_and_never_exposes_unbounded_input():
    retriever = public_reference_retriever()
    reasons = (
        (FindingFamily.COUNTERPARTY, "INVOICE_FIELDS_UNCONFIRMED"),
        (FindingFamily.COUNTERPARTY, "INVOICE_AMOUNT_CONFLICT"),
        (FindingFamily.SETTLEMENT, "PAYMENT_IDENTITY_UNVERIFIED"),
    )

    found = candidate_passages_for_reasons(retriever, reasons, as_of=date(2026, 9, 26))

    assert found
    assert len({item.rule_id for item in found}) == len(found)
    assert all(item.jurisdiction == "TN" for item in found)
    assert all("DEMO-MF-BAT" not in item.text for item in found)
    assert candidate_passages_for_reasons(retriever, reasons, as_of=date(2026, 9, 26), audience=Audience.COMPANY) == ()
