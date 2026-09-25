import hashlib
from pathlib import Path

from boussla.documents.integrity import PdfIntegrityInspector

from test_native_text import document


FIXTURE = Path("docs/build_lock/fixtures/documents/01_buyer_invoice.pdf")


def test_inventory_hashes_original_bytes_without_authenticity_verdict():
    content = FIXTURE.read_bytes()
    report = PdfIntegrityInspector().inspect(document(), content)

    assert report.sha256 == hashlib.sha256(content).hexdigest()
    assert report.signature_status == "UNSIGNED"
    assert report.c2pa_status == "NOT_CHECKED"
    assert report.ai_origin == "UNKNOWN"
    assert report.metadata["pdf_producer"]
    assert report.metadata["acquisition_channel"] == "COMPANY_UPLOAD"
    assert "HASH_IS_NOT_AUTHENTICITY" in report.limitations


def test_recorded_hash_mismatch_is_reported_without_forgery_claim():
    content = FIXTURE.read_bytes()
    changed_record = document().model_copy(update={"sha256": "0" * 64})

    report = PdfIntegrityInspector().inspect(changed_record, content)

    assert "HASH_MISMATCH_WITH_RECORD" in report.limitations
    assert report.sha256 == hashlib.sha256(content).hexdigest()


def test_unreadable_pdf_keeps_hash_and_reports_inspection_limit():
    report = PdfIntegrityInspector().inspect(document(), b"not a PDF")

    assert report.sha256 == hashlib.sha256(b"not a PDF").hexdigest()
    assert report.signature_status == "UNSUPPORTED"
    assert "UNREADABLE_PDF" in report.limitations
