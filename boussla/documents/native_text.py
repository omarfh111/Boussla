"""Bounded native PDF text extraction. Returned text is untrusted source data."""

from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from boussla.contracts import Document, DocumentText, PageText


class NativePdfExtractor:
    """Extract one-based page text without OCR, rendering or network access."""

    def __init__(
        self, max_bytes: int = 10_000_000, max_pages: int = 5, max_text_chars: int = 100_000
    ) -> None:
        if min(max_bytes, max_pages, max_text_chars) < 1:
            raise ValueError("extraction limits must be positive")
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_text_chars = max_text_chars

    def extract_text(self, document: Document, content: bytes) -> DocumentText:
        def unsupported(reason: str) -> DocumentText:
            return DocumentText(document_id=document.document_id, pages=(), status="UNSUPPORTED", limitations=(reason,))

        if len(content) > self.max_bytes:
            return unsupported("LIMIT_EXCEEDED")
        if document.media_type != "application/pdf" or not content.startswith(b"%PDF-"):
            return unsupported("UNSUPPORTED_FILE")
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                return unsupported("ENCRYPTED_PDF")
            if len(reader.pages) > self.max_pages:
                return unsupported("LIMIT_EXCEEDED")
            pages: list[PageText] = []
            total_chars = 0
            for number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                total_chars += len(text)
                if total_chars > self.max_text_chars:
                    return unsupported("TEXT_LIMIT_EXCEEDED")
                pages.append(PageText(page=number, text=text))
        except (PdfReadError, OSError, ValueError, TypeError):
            return unsupported("UNREADABLE_PDF")

        if not any(page.text.strip() for page in pages):
            return unsupported("NO_NATIVE_TEXT_MANUAL_REVIEW")
        limitations = ("SOME_PAGES_HAVE_NO_NATIVE_TEXT",) if any(not page.text.strip() for page in pages) else ()
        return DocumentText(
            document_id=document.document_id,
            pages=tuple(pages),
            status="PARTIAL" if limitations else "OK",
            limitations=limitations,
        )
