"""Apply attributed corrections without manufacturing supporting source spans."""
from __future__ import annotations

from boussla.contracts import BousslaError, CandidateField, DocumentText, ErrorCode, ExtractionProposal


def confirm_fields(proposal: ExtractionProposal, fields: dict[str, str],
                   text: DocumentText | None) -> ExtractionProposal:
    known = {c.field_name for c in proposal.candidates} | set(proposal.missing_fields)
    if not fields or not set(fields) <= known or any(not isinstance(v, str) for v in fields.values()):
        raise BousslaError(ErrorCode.INVALID_INPUT, "Champs de confirmation invalides")
    # Re-read labelled fields so normalized quantities can recover their exact source
    # (e.g. 1000 versus "1 000") without citing an unrelated occurrence elsewhere.
    fresh = None
    if text is not None:
        from boussla.documents.allocation import KnownLayoutAllocationExtractor
        fresh = KnownLayoutAllocationExtractor().extract_fields(text)
    source_fields = {c.field_name: c for c in fresh.candidates} if fresh else {}
    result = []
    for candidate in proposal.candidates:
        if candidate.field_name not in fields:
            result.append(candidate if proposal.status == "CONFIRMED" else candidate.model_copy(update={
                "ambiguities": tuple(dict.fromkeys((*candidate.ambiguities, "FIELD_NOT_CONFIRMED")))}))
            continue
        value = fields[candidate.field_name].strip()
        if value and value in (candidate.raw_value, candidate.normalized_value):
            result.append(candidate.model_copy(update={"ambiguities": tuple(a for a in candidate.ambiguities if a != "FIELD_NOT_CONFIRMED")}))
            continue
        original = source_fields.get(candidate.field_name)
        if original is not None and value in (original.raw_value, original.normalized_value):
            result.append(original)
            continue
        refs = ()
        # A changed value is an attributed correction. Only a real span can support coherence.
        result.append(CandidateField(field_name=candidate.field_name, raw_value=value or None,
            normalized_value=value or None, evidence_refs=refs,
            ambiguities=() if refs else ("MANUAL_CORRECTION_WITHOUT_SOURCE",)))
    missing = tuple(c.field_name for c in result if c.normalized_value is None)
    pending = any("FIELD_NOT_CONFIRMED" in c.ambiguities for c in result)
    return proposal.model_copy(update={"candidates": tuple(result), "missing_fields": missing,
                                       "status": "PROPOSED" if pending else "CONFIRMED"})
