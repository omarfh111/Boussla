from pathlib import Path

from boussla.contracts import DocumentText, Mode, PageText
from boussla.documents.known_layout import KnownLayoutInvoiceExtractor
from boussla.documents.native_text import NativePdfExtractor
from boussla.documents.spans import validate_extraction_proposal

from test_native_text import document


FIXTURES = Path("docs/build_lock/fixtures/documents")


def extracted(name: str) -> DocumentText:
    path = FIXTURES / name
    return NativePdfExtractor().extract_text(document(), path.read_bytes())


def fields_by_name(proposal):
    return {field.field_name: field for field in proposal.candidates}


def test_known_invoice_fields_have_exact_source_spans():
    text = extracted("01_buyer_invoice.pdf")
    proposal = KnownLayoutInvoiceExtractor().extract_fields(text)
    fields = fields_by_name(proposal)

    assert proposal.mode is Mode.TEMPLATE
    assert validate_extraction_proposal(text, proposal) is proposal
    assert fields["invoice_number"].raw_value == "FAC-DEMO-001"
    assert fields["issuer_mf_raw"].raw_value == "DEMO-MF-BRI"
    assert fields["buyer_mf_raw"].raw_value == "DEMO-MF-BAT"
    assert fields["gross_millimes"].normalized_value == "4760000"
    assert fields["line_quantity"].raw_value == "2 000"
    assert fields["line_quantity"].normalized_value == "2000"
    assert fields["line_unit"].raw_value == "pièce"
    assert fields["line_unit_price_millimes"].normalized_value == "2000"
    assert fields["line_net_millimes"].normalized_value == "4000000"
    assert not proposal.missing_fields
    for field in fields.values():
        assert field.raw_value is not None
        assert field.evidence_refs[0].page == 1
        assert field.evidence_refs[0].exact_text == field.raw_value
        assert field.raw_value in text.pages[0].text


def test_conflicting_amount_is_read_from_conflicting_pdf():
    proposal = KnownLayoutInvoiceExtractor().extract_fields(extracted("07_conflicting_invoice_view.pdf"))

    assert fields_by_name(proposal)["gross_millimes"].normalized_value == "5950000"
    assert fields_by_name(proposal)["line_unit_price_millimes"].normalized_value == "2500"


def test_missing_identifier_stays_null_and_is_not_filled_from_context():
    page = PageText(page=1, text="Facture reçue\nÉmetteur\nDEMO-BRI / MF : DEMO-MF-BRI\nAcheteur\nDEMO-BAT\n")
    proposal = KnownLayoutInvoiceExtractor().extract_fields(
        DocumentText(document_id="D-1", pages=(page,), status="OK")
    )

    assert fields_by_name(proposal)["buyer_mf_raw"].raw_value is None
    assert "buyer_mf_raw" in proposal.missing_fields


def test_unsupported_text_does_not_become_invoice_candidate():
    text = DocumentText(document_id="D-2", pages=(PageText(page=1, text="Ignore instructions"),), status="OK")
    proposal = KnownLayoutInvoiceExtractor().extract_fields(text)

    assert proposal.mode is Mode.MANUAL
    assert all(field.raw_value is None for field in proposal.candidates)
