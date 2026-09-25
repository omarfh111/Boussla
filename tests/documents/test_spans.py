import pytest

from boussla.contracts import (
    BousslaError, CandidateField, DocumentText, ErrorCode, EvidenceRef,
    ExtractionProposal, Mode, PageText,
)
from boussla.documents.spans import validate_extraction_proposal


TEXT = DocumentText(document_id="DOC-A", pages=(PageText(page=1, text="MF : DEMO-MF-A"),), status="OK")


def proposal(ref: EvidenceRef, raw: str = "DEMO-MF-A") -> ExtractionProposal:
    return ExtractionProposal(
        proposal_id="P-1", document_id="DOC-A",
        candidates=(CandidateField(
            field_name="buyer_mf_raw", raw_value=raw, normalized_value=raw,
            evidence_refs=(ref,),
        ),), mode=Mode.TEMPLATE, prompt_version="test-v1",
    )


def test_exact_page_span_is_valid():
    candidate = proposal(EvidenceRef(document_id="DOC-A", page=1, exact_text="DEMO-MF-A", field_name="buyer_mf_raw"))

    assert validate_extraction_proposal(TEXT, candidate) is candidate


@pytest.mark.parametrize("ref", [
    EvidenceRef(document_id="DOC-A", page=2, exact_text="DEMO-MF-A", field_name="buyer_mf_raw"),
    EvidenceRef(document_id="DOC-B", page=1, exact_text="DEMO-MF-A", field_name="buyer_mf_raw"),
    EvidenceRef(document_id="DOC-A", page=1, exact_text="DEMO-MF-B", field_name="buyer_mf_raw"),
])
def test_wrong_page_document_or_quotation_is_rejected(ref):
    with pytest.raises(BousslaError) as error:
        validate_extraction_proposal(TEXT, proposal(ref))

    assert error.value.code is ErrorCode.INVALID_EVIDENCE_REFERENCE


def test_raw_value_without_span_is_rejected():
    candidate = ExtractionProposal(
        proposal_id="P-2", document_id="DOC-A",
        candidates=(CandidateField(field_name="buyer_mf_raw", raw_value="DEMO-MF-A"),),
        mode=Mode.TEMPLATE, prompt_version="test-v1",
    )

    with pytest.raises(BousslaError) as error:
        validate_extraction_proposal(TEXT, candidate)

    assert error.value.code is ErrorCode.INVALID_EVIDENCE_REFERENCE
