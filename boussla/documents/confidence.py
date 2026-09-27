"""Deterministic quality-of-analysis index, never an authenticity probability."""
from decimal import Decimal, ROUND_HALF_UP
from boussla.contracts import DocumentConfidence, DocumentConfidenceFactor

WEIGHTS = {"EXTRACTION":35,"INTERNAL_COHERENCE":30,"EXTERNAL_CONCORDANCE":25,"BYTE_INTEGRITY":10}


def calculate_document_confidence(extraction, checks, classification):
    by_code = {c.code:c for c in checks}
    fields = {f.field_name for f in extraction.candidates if f.normalized_value is not None
              and f.evidence_refs and not f.ambiguities} if extraction else set()
    required = [("invoice_number",),("issued_on",),("currency",),("issuer_mf_raw","issuer_company_id"),
                ("buyer_mf_raw","buyer_company_id"),("net_millimes",),("tax_millimes",),("gross_millimes",)]
    if classification != "INVOICE":
        required = [(f.field_name,) for f in extraction.candidates] if extraction else []
    values = {"EXTRACTION": int(Decimal(sum(bool(fields.intersection(group)) for group in required))*100/len(required))
              if required and extraction else None}
    internal = [by_code[c] for c in ("TOTAL_ARITHMETIC","LINE_ARITHMETIC","TAX_ARITHMETIC","ISSUE_DATE")
                if c in by_code and by_code[c].status != "UNKNOWN"]
    values["INTERNAL_COHERENCE"] = int(Decimal(sum(c.status == "PASS" for c in internal))*100/len(internal)) if internal else None
    external = [by_code[c] for c in ("DOSSIER_CONCORDANCE","RESPONSE_CONCORDANCE","COMPANY_SCOPE")
                if c in by_code and by_code[c].status != "UNKNOWN"]
    values["EXTERNAL_CONCORDANCE"] = int(Decimal(sum(c.status == "PASS" for c in external))*100/len(external)) if external else None
    integrity = by_code.get("BYTE_INTEGRITY")
    values["BYTE_INTEGRITY"] = 100 if integrity and integrity.status == "PASS" else 0 if integrity and integrity.status == "FAIL" else None
    count = sum(v is not None for v in values.values())
    score = None
    if count >= 3 and values["EXTRACTION"] is not None:
        measured = sum(WEIGHTS[k] for k,v in values.items() if v is not None)
        score = int((sum(Decimal(v)*WEIGHTS[k] for k,v in values.items() if v is not None)/measured).quantize(Decimal(1),rounding=ROUND_HALF_UP))
        if any(c.status == "FAIL" for c in checks):
            score = min(score,39)
        elif any(c.status == "WARN" for c in checks):
            score = min(score,59)
    explanation = {
        "EXTRACTION":"Complétude des champs sourcés sans ambiguïté ; pas une précision statistique du modèle.",
        "INTERNAL_COHERENCE":"Part des contrôles arithmétiques et de date exécutables qui concordent.",
        "EXTERNAL_CONCORDANCE":"Concordance avec le dossier et la réponse ; aucun registre externe vérifié.",
        "BYTE_INTEGRITY":"Conservation de l’empreinte des octets ; aucune mesure d’authenticité ou d’absence de retouche.",
    }
    refs = {
        "EXTRACTION":tuple(sorted({r.document_id for f in extraction.candidates for r in f.evidence_refs if r.document_id})) if extraction else (),
        "INTERNAL_COHERENCE":tuple(sorted({s for c in internal for s in c.source_ids})),
        "EXTERNAL_CONCORDANCE":tuple(sorted({s for c in external for s in c.source_ids})),
        "BYTE_INTEGRITY":integrity.source_ids if integrity else (),
    }
    factors = tuple(DocumentConfidenceFactor(code=k,value=v,status="MEASURED" if v is not None else "UNKNOWN",
        explanation_fr=explanation[k],source_ids=refs[k]) for k,v in values.items())
    return DocumentConfidence(value=score,level="INSUFFICIENT_DATA" if score is None else "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW",
        factors=factors,measured_dimensions=count,rule_version="document-confidence-1",
        explanation_fr="Indice de qualité des contrôles disponibles : poids 35/30/25/10 renormalisés, au moins trois dimensions. Une contradiction plafonne l’indice à 39, un signal à 59. Ce n’est pas une probabilité d’authenticité et cela ne résout aucune cause.")
