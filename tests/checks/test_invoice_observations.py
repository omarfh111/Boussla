"""Evidence and arithmetic checks for the first lane B invoice increment."""

import json
from datetime import datetime
from pathlib import Path

from boussla.checks import compare_invoice_observations
from boussla.contracts import (
    AcquisitionChannel, Document, FindingStatus, InvoiceObservation,
    Transaction, TransactionInputs,
)

OBSERVED = Path(__file__).resolve().parents[2] / "docs" / "build_lock" / "fixtures" / "observed"


def _rows(name):
    return json.loads((OBSERVED / name).read_text(encoding="utf-8"))


def _inputs():
    transaction = Transaction.model_validate({
        key: value for key, value in _rows("transactions.json")[0].items()
        if key in Transaction.model_fields
    })
    observations = tuple(InvoiceObservation.model_validate(row) for row in _rows("invoice_observations.json"))
    documents = tuple(Document.model_validate({
        key: value for key, value in row.items() if key in Document.model_fields
    }) for row in _rows("documents.json") if row["document_id"] in {o.document_id for o in observations})
    return TransactionInputs(
        case_id="CASE-BRICKS-001", company_id="DEMO-BAT", case_version=1,
        as_of=datetime.fromisoformat("2026-09-25T12:00:00+01:00"),
        transaction=transaction, invoice_observations=observations, documents=documents,
    )


def _replace(inputs, *, observation=None, document=None):
    observations = tuple(observation if o.observation_id == observation.observation_id else o
                         for o in inputs.invoice_observations) if observation else inputs.invoice_observations
    documents = tuple(document if d.document_id == document.document_id else d
                      for d in inputs.documents) if document else inputs.documents
    return inputs.model_copy(update={"invoice_observations": observations, "documents": documents})


def test_independent_matching_views_are_one_transaction():
    inputs = _inputs()
    finding = compare_invoice_observations(inputs)
    assert finding.status is FindingStatus.EXPLAINED
    assert finding.severity == "0"
    assert finding.transaction_id == inputs.transaction.transaction_id
    assert {ref.document_id for ref in finding.evidence_refs} == {"DOC-BUY-001", "DOC-SELL-001"}


def test_gross_conflict_reports_exact_gap_and_sources():
    inputs = _inputs()
    buyer = inputs.invoice_observations[0].model_copy(update={"gross_millimes": 5950000})
    finding = compare_invoice_observations(_replace(inputs, observation=buyer))
    assert finding.status is FindingStatus.UNRESOLVED
    assert finding.financial_basis == "GROSS_TTC"
    assert finding.observed_difference_millimes == 1190000
    assert finding.severity == "1"
    assert {ref.field_name for ref in finding.evidence_refs} == {"gross_millimes"}


def test_same_origin_copy_does_not_establish_independence():
    inputs = _inputs()
    seller = inputs.invoice_observations[1].model_copy(update={"origin_group_id": "COMPANY-DEMO-BAT"})
    seller_doc = inputs.documents[1].model_copy(update={
        "origin_group_id": "COMPANY-DEMO-BAT", "acquisition_channel": AcquisitionChannel.COMPANY_UPLOAD,
    })
    finding = compare_invoice_observations(_replace(inputs, observation=seller, document=seller_doc))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "INDEPENDENT_COUNTERPARTY_NOT_ESTABLISHED"
    assert finding.severity is None


def test_missing_or_future_seller_view_is_unknown():
    inputs = _inputs()
    only_buyer = inputs.model_copy(update={"invoice_observations": inputs.invoice_observations[:1]})
    assert compare_invoice_observations(only_buyer).status is FindingStatus.INSUFFICIENT
    seller = inputs.invoice_observations[1].model_copy(update={
        "available_at": datetime.fromisoformat("2026-10-01T12:00:00+01:00"),
    })
    assert compare_invoice_observations(_replace(inputs, observation=seller)).status is FindingStatus.INSUFFICIENT


def test_wrong_company_evidence_is_not_a_scored_conflict():
    inputs = _inputs()
    seller = inputs.invoice_observations[1].model_copy(update={"buyer_company_id": "OTHER-COMPANY"})
    finding = compare_invoice_observations(_replace(inputs, observation=seller))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "WRONG_COMPANY_OR_ISSUER"


def test_different_invoice_number_is_ambiguous_linkage():
    inputs = _inputs()
    seller = inputs.invoice_observations[1].model_copy(update={"invoice_number": "OTHER-INVOICE"})
    finding = compare_invoice_observations(_replace(inputs, observation=seller))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "INVOICE_LINKAGE_AMBIGUOUS"


def test_matching_totals_do_not_hide_line_quantity_conflict():
    inputs = _inputs()
    seller = inputs.invoice_observations[1]
    changed_line = seller.lines[0].model_copy(update={"quantity": "1500"})
    seller = seller.model_copy(update={"lines": (changed_line,)})
    finding = compare_invoice_observations(_replace(inputs, observation=seller))
    assert finding.status is FindingStatus.UNRESOLVED
    assert finding.reason_code == "INVOICE_LINE_QUANTITY_CONFLICT"
    assert finding.quantity_difference == "500"
    assert finding.unit == "piece"


def test_unsupported_multiple_lines_do_not_claim_a_match():
    inputs = _inputs()
    seller = inputs.invoice_observations[1]
    seller = seller.model_copy(update={"lines": (*seller.lines, seller.lines[0])})
    finding = compare_invoice_observations(_replace(inputs, observation=seller))
    assert finding.status is FindingStatus.INSUFFICIENT
    assert finding.reason_code == "LINE_COMPARISON_UNSUPPORTED"
