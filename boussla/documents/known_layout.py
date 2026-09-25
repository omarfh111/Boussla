"""Deterministic candidate fields for the supplied French invoice layout family."""

from __future__ import annotations

import hashlib
import re

from boussla.contracts import CandidateField, DocumentText, EvidenceRef, ExtractionProposal, Mode


FIELDS = (
    "invoice_number", "issuer_mf_raw", "buyer_mf_raw", "issued_on",
    "currency", "net_millimes", "tax_millimes", "gross_millimes",
)
PATTERNS = {
    "invoice_number": re.compile(r"(?m)^Référence\s*\n([^\s/]+)"),
    "issuer_mf_raw": re.compile(r"(?m)^Émetteur\s*\n[^\n]*?MF\s*:\s*(\S+)"),
    "buyer_mf_raw": re.compile(r"(?m)^Acheteur\s*\n[^\n]*?MF\s*:\s*(\S+)"),
    "issued_on": re.compile(r"(?m)^Date\s*\n(\d{4}-\d{2}-\d{2})"),
    "currency": re.compile(r"(?m)^Devise\s*\n([A-Z]{3})"),
}
AMOUNTS = re.compile(
    r"(?s)Montants\s*\nHT\s*:\s*(?P<net>[\d ]+,\d{3})\s*DT\s*\|\s*"
    r"Taxe de scénario\s*:\s*(?P<tax>[\d ]+,\d{3})\s*DT\s*\|\s*"
    r"TTC\s*:\s*(?P<gross>[\d ]+,\d{3})\s*DT"
)


def _millimes(raw: str) -> str:
    whole, fractional = raw.replace(" ", "").split(",")
    return str(int(whole) * 1000 + int(fractional))


class KnownLayoutInvoiceExtractor:
    """Produces proposals only; no case context, truth keys or acceptance."""

    def extract_fields(self, text: DocumentText) -> ExtractionProposal:
        digest = hashlib.sha256("\n".join(p.text for p in text.pages).encode()).hexdigest()[:12]
        supported = text.status in ("OK", "PARTIAL") and any(
            re.search(r"(?im)facture", page.text)
            and re.search(r"(?m)^Émetteur\s*$", page.text)
            and re.search(r"(?m)^Acheteur\s*$", page.text)
            for page in text.pages
        )
        matches: dict[str, tuple[str, int]] = {}
        if supported:
            for page in text.pages:
                for field, pattern in PATTERNS.items():
                    if field not in matches and (match := pattern.search(page.text)):
                        matches[field] = (match.group(1), page.page)
                if amount_match := AMOUNTS.search(page.text):
                    for field, group in (("net_millimes", "net"), ("tax_millimes", "tax"), ("gross_millimes", "gross")):
                        if field not in matches:
                            matches[field] = (amount_match.group(group), page.page)

        candidates = []
        for field in FIELDS:
            raw, page = matches.get(field, (None, None))
            normalized = _millimes(raw) if raw is not None and field.endswith("_millimes") else raw
            refs = (EvidenceRef(document_id=text.document_id, page=page, exact_text=raw, field_name=field),) if raw else ()
            candidates.append(CandidateField(
                field_name=field, raw_value=raw, normalized_value=normalized,
                evidence_refs=refs, ambiguities=("UNSUPPORTED_LAYOUT",) if not supported else (),
            ))
        return ExtractionProposal(
            proposal_id=f"PARSE-{text.document_id}-{digest}", document_id=text.document_id,
            candidates=tuple(candidates),
            missing_fields=tuple(field for field in FIELDS if field not in matches),
            mode=Mode.TEMPLATE if supported else Mode.MANUAL,
            prompt_version="known-layout-v1",
        )
