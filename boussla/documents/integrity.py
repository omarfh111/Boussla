"""Read-only PDF byte and provenance inventory, without authenticity claims."""

from __future__ import annotations

import hashlib
from io import BytesIO

from pypdf import PdfReader

from boussla.contracts import Document, IntegrityReport


class PdfIntegrityInspector:
    def inspect(self, document: Document, content: bytes) -> IntegrityReport:
        digest = hashlib.sha256(content).hexdigest()
        limitations = ["HASH_IS_NOT_AUTHENTICITY", "SIGNATURE_TRUST_NOT_VALIDATED", "C2PA_NOT_CHECKED"]
        if digest != document.sha256:
            limitations.append("HASH_MISMATCH_WITH_RECORD")
        metadata = {
            "acquisition_channel": document.acquisition_channel.value,
            "origin_group_id": document.origin_group_id,
        }
        signature_status = "UNSUPPORTED"
        try:
            if not content.startswith(b"%PDF-"):
                raise ValueError("unsupported PDF header")
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                limitations.append("ENCRYPTED_PDF")
            else:
                info = reader.metadata
                if info:
                    for key, name in (
                        ("/Producer", "pdf_producer"), ("/Creator", "pdf_creator"),
                        ("/CreationDate", "pdf_creation_date"), ("/ModDate", "pdf_modification_date"),
                    ):
                        value = info.get(key)
                        if value is not None:
                            metadata[name] = str(value)
                fields = reader.get_fields() or {}
                signature_status = "NOT_CHECKED" if any(
                    field.get("/FT") == "/Sig" for field in fields.values()
                ) else "UNSIGNED"
        except Exception:
            limitations.append("UNREADABLE_PDF")
        return IntegrityReport(
            document_id=document.document_id,
            sha256=digest,
            metadata=metadata,
            signature_status=signature_status,
            limitations=tuple(limitations),
        )
