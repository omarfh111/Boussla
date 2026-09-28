"""Source-only extraction for labelled native allocation records; no case defaults."""
from __future__ import annotations

import hashlib
import re

from boussla.contracts import CandidateField, DocumentText, EvidenceRef, ExtractionProposal, Mode
from boussla.documents.spans import validate_extraction_proposal


class KnownLayoutAllocationExtractor:
    def extract_fields(self, text: DocumentText) -> ExtractionProposal | None:
        if text.status not in ("OK", "PARTIAL"):
            return None
        candidates = []
        seen = set()
        def add(name, raw, page, normalized=None):
            if name in seen:
                for index, prior in enumerate(candidates):
                    if prior.field_name == name and prior.normalized_value != (normalized if normalized is not None else raw):
                        candidates[index] = prior.model_copy(update={"ambiguities": ("CONFLICTING_SOURCE_FIELDS",)})
                return
            seen.add(name)
            candidates.append(CandidateField(field_name=name, raw_value=raw,
                normalized_value=normalized if normalized is not None else raw,
                evidence_refs=(EvidenceRef(document_id=text.document_id, page=page,
                                          exact_text=raw, field_name=name),)))
        for page in text.pages:
            if not re.search(r"(?im)^Affectation propos[ée]e\s*$", page.text):
                continue
            match = re.search(r"(?m)^Transaction et ligne\s*\n([^ /\n]+) / ([^ /\n]+)", page.text)
            if match:
                add("allocation.transaction_id", match[1], page.page)
                add("allocation.line_id", match[2], page.page)
            company = re.search(r"(?m)^Entreprise\s*\n([^\n]+)", page.text)
            if company:
                add("allocation.company_id", company[1].strip(), page.page)
            proposed = re.search(r"(?m)^Affectation propos[ée]e\s*\n([^\n]+)", page.text)
            if proposed:
                for item in re.finditer(r"([A-Za-z0-9_-]+)\s*:\s*([0-9][0-9 \u00a0]*(?:[.,][0-9]+)?)", proposed[1]):
                    raw = item[2].strip()
                    add(f"allocation.{item[1]}.quantity", raw, page.page,
                        raw.replace(" ", "").replace("\u00a0", "").replace(",", "."))
        if not candidates:
            return None
        digest = hashlib.sha256(text.model_dump_json().encode()).hexdigest()[:12]
        result = ExtractionProposal(proposal_id=f"EXT-ALLOC-{digest}", document_id=text.document_id,
            candidates=tuple(candidates), mode=Mode.TEMPLATE, prompt_version="native-allocation-1")
        return validate_extraction_proposal(text, result)
