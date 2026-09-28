from boussla.contracts import CandidateField, EvidenceRef, ExtractionProposal, DocumentCheck, Mode
from boussla.documents.confidence import calculate_document_confidence


def extraction():
    return ExtractionProposal(proposal_id="E",document_id="D",mode=Mode.TEMPLATE,prompt_version="test",
        candidates=(CandidateField(field_name="reference",raw_value="R",normalized_value="R",
            evidence_refs=(EvidenceRef(document_id="D",page=1,exact_text="R",field_name="reference"),)),))


def checks(status="PASS"):
    return [DocumentCheck(code=code,status=status,explanation_fr="Test",source_ids=("D",))
            for code in ("ISSUE_DATE","DOSSIER_CONCORDANCE","BYTE_INTEGRITY")]


def test_unknown_dimensions_do_not_become_zero_or_high_confidence():
    result = calculate_document_confidence(None,[],"OTHER_OR_UNKNOWN")
    assert result.value is None and result.level == "INSUFFICIENT_DATA"
    assert all(f.value is None for f in result.factors)
    result = calculate_document_confidence(extraction(),checks("UNKNOWN"),"CONTRACT")
    assert result.value is None and result.measured_dimensions == 1


def test_available_dimensions_have_explicit_sources_and_renormalized_weights():
    result = calculate_document_confidence(extraction(),checks(),"CONTRACT")
    assert result.value == 100 and result.measured_dimensions == 4
    assert all(f.source_ids for f in result.factors)
    assert result.rule_version == "document-confidence-1"


def test_contradiction_and_warning_cap_an_otherwise_high_index():
    broken = checks()+[DocumentCheck(code="TOTAL_ARITHMETIC",status="FAIL",explanation_fr="Mismatch")]
    assert calculate_document_confidence(extraction(),broken,"CONTRACT").value <= 39
    warning = checks()+[DocumentCheck(code="METADATA_CHRONOLOGY",status="WARN",explanation_fr="Review")]
    assert calculate_document_confidence(extraction(),warning,"CONTRACT").value <= 59


def test_invoice_requires_header_coverage_not_only_one_successful_field():
    result = calculate_document_confidence(extraction(),checks(),"INVOICE")
    assert result.factors[0].value == 0 and result.value < 80
