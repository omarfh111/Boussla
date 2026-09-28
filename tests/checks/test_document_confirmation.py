"""A correction cannot retain an unrelated source span or confirm other fields."""
from boussla.contracts import CandidateField, DocumentText, EvidenceRef, ExtractionProposal, Mode, PageText
from boussla.documents.confirmation import confirm_fields
from boussla.documents.allocation import KnownLayoutAllocationExtractor


def source():
    text = DocumentText(document_id="D", status="OK", pages=(PageText(page=1, text="1000 900"),))
    proposal = ExtractionProposal(proposal_id="E", document_id="D", mode=Mode.TEMPLATE,
        prompt_version="test", candidates=tuple(CandidateField(field_name=name, raw_value="1000",
            normalized_value="1000", evidence_refs=(EvidenceRef(document_id="D", page=1,
            exact_text="1000", field_name=name),)) for name in ("a", "b")))
    return text, proposal


def test_changed_value_is_applied_and_unsupported_correction_loses_source():
    text, proposal = source()
    result = confirm_fields(proposal, {"a": "800", "b": "900"}, text)
    assert result.candidates[0].normalized_value == "800"
    assert result.candidates[0].evidence_refs == ()
    # A number elsewhere on the page is not proof of this field.
    assert result.candidates[1].evidence_refs == ()


def test_partial_confirmation_does_not_confirm_untouched_fields():
    text, proposal = source()
    result = confirm_fields(proposal, {"a": "1000"}, text)
    assert result.status == "PROPOSED"
    assert "FIELD_NOT_CONFIRMED" in result.candidates[1].ambiguities


def test_allocation_extraction_uses_actual_text_and_arbitrary_project_ids():
    text = DocumentText(document_id="D", status="OK", pages=(PageText(page=1, text=
        "Entreprise\nCOMP-X\nTransaction et ligne\nTX-X / LINE-X / ITEM\n"
        "Affectation initiale\nSITE-A : 9 000 pièces\nAffectation proposée\n"
        "SITE-A : 1 000 pièces / SITE-B : 900 pièces\n"),))
    result = KnownLayoutAllocationExtractor().extract_fields(text)
    values = {c.field_name: c.normalized_value for c in result.candidates}
    assert values["allocation.transaction_id"] == "TX-X"
    assert values["allocation.SITE-A.quantity"] == "1000"
    assert values["allocation.SITE-B.quantity"] == "900"
    assert result.status == "PROPOSED"
    assert KnownLayoutAllocationExtractor().extract_fields(text.model_copy(update={"pages": ()})) is None


def test_conflicting_quantities_are_not_confirmed_away():
    text = DocumentText(document_id="D", status="OK", pages=(PageText(page=1, text=
        "Affectation proposée\nP1 : 1 000 pièces / P1 : 900 pièces\n"),))
    proposal = KnownLayoutAllocationExtractor().extract_fields(text)
    result = confirm_fields(proposal, {"allocation.P1.quantity": "1000"}, text)
    assert result.candidates[0].ambiguities == ("CONFLICTING_SOURCE_FIELDS",)
