from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter

from boussla.contracts import AcquisitionChannel, Document
from boussla.documents.native_text import NativePdfExtractor


FIXTURE = Path("docs/build_lock/fixtures/documents/01_buyer_invoice.pdf")


def document() -> Document:
    return Document(
        document_id="DOC-BUY-001",
        subject_company_id="DEMO-BAT",
        case_id="CASE-BRICKS-001",
        original_filename=FIXTURE.name,
        local_path=str(FIXTURE),
        sha256="67581d2bce727bd661e3cf7f3a226203881652586509e5b8a7d404bbf2fac95b",
        media_type="application/pdf",
        received_at=datetime.now(timezone.utc),
        uploader_actor_id="DEMO-COMPANY-BAT",
        acquisition_channel=AcquisitionChannel.COMPANY_UPLOAD,
        origin_group_id="COMPANY-DEMO-BAT",
        confidentiality_scope="CASE_PARTIES",
    )


def test_fixture_returns_page_indexed_native_text():
    result = NativePdfExtractor().extract_text(document(), FIXTURE.read_bytes())

    assert result.status == "OK"
    assert len(result.pages) == 1
    assert result.pages[0].page == 1
    assert "FAC-DEMO-001" in result.pages[0].text
    assert "DEMO-MF-BAT" in result.pages[0].text


def test_rejects_oversize_before_pdf_parsing():
    result = NativePdfExtractor(max_bytes=8).extract_text(document(), b"%PDF-" + b"x" * 16)

    assert result.status == "UNSUPPORTED"
    assert result.pages == ()
    assert "LIMIT_EXCEEDED" in result.limitations


def test_rejects_non_pdf_content():
    result = NativePdfExtractor().extract_text(document(), b"not a PDF")

    assert result.status == "UNSUPPORTED"
    assert "UNSUPPORTED_FILE" in result.limitations


def test_page_limit_is_explicit():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.add_blank_page(width=100, height=100)
    content = BytesIO()
    writer.write(content)

    result = NativePdfExtractor(max_pages=1).extract_text(document(), content.getvalue())

    assert result.status == "UNSUPPORTED"
    assert result.pages == ()
    assert "LIMIT_EXCEEDED" in result.limitations


def test_image_only_pdf_has_manual_fallback_status():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    content = BytesIO()
    writer.write(content)

    result = NativePdfExtractor().extract_text(document(), content.getvalue())

    assert result.status == "UNSUPPORTED"
    assert "NO_NATIVE_TEXT_MANUAL_REVIEW" in result.limitations


def test_encrypted_pdf_is_unsupported():
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("demo-password")
    content = BytesIO()
    writer.write(content)

    result = NativePdfExtractor().extract_text(document(), content.getvalue())

    assert result.status == "UNSUPPORTED"
    assert "ENCRYPTED_PDF" in result.limitations
