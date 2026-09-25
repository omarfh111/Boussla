"""Reject candidate values without a verifiable source span in this document."""

from boussla.contracts import BousslaError, DocumentText, ErrorCode, ExtractionProposal


def validate_extraction_proposal(text: DocumentText, proposal: ExtractionProposal) -> ExtractionProposal:
    def invalid() -> None:
        raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE, "Candidate source span is invalid")

    if text.document_id != proposal.document_id:
        invalid()
    pages = {page.page: page.text for page in text.pages}
    seen: set[str] = set()
    for field in proposal.candidates:
        if field.field_name in seen:
            invalid()
        seen.add(field.field_name)
        if field.raw_value is None:
            if field.evidence_refs or field.field_name not in proposal.missing_fields:
                invalid()
            continue
        if field.field_name in proposal.missing_fields or not field.evidence_refs:
            invalid()
        for ref in field.evidence_refs:
            if (
                ref.document_id != text.document_id
                or ref.field_name != field.field_name
                or ref.page not in pages
                or not ref.exact_text
                or ref.exact_text not in pages[ref.page]
                or field.raw_value not in ref.exact_text
            ):
                invalid()
    if set(proposal.missing_fields) - seen:
        invalid()
    return proposal
