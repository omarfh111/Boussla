"""Conservative native labelled fields, never case- or filename-derived."""
import hashlib
import re
from decimal import Decimal, InvalidOperation
from boussla.contracts import CandidateField, DocumentClass, EvidenceRef, ExtractionProposal, Mode
from boussla.documents.spans import validate_extraction_proposal

LABELS = {
    "reference": r"Référence|Reference|Numéro|Numero",
    "transaction_id": r"Transaction|Identifiant transaction",
    "company_id": r"Entreprise|Identifiant entreprise",
    "issuer_company_id": r"Fournisseur|Vendeur|Émetteur",
    "buyer_company_id": r"Acheteur|Client",
    "project_id": r"Projet",
    "period": r"Période|Periode",
    "issued_on": r"Date",
    "currency": r"Devise",
    "net_millimes": r"HT|Montant HT",
    "tax_millimes": r"TVA|Montant TVA",
    "gross_millimes": r"TTC|Montant TTC",
    "line_quantity": r"Quantité|Quantite",
    "tax_rate": r"Taux TVA",
}

def classify_native(text):
    if text is None or text.status not in ("OK","PARTIAL"):
        return DocumentClass.OTHER_OR_UNKNOWN
    title = "\n".join(text.pages[0].text.splitlines()[:5]).casefold() if text.pages else ""
    for words, kind in ((r"bon de livraison|bordereau de livraison",DocumentClass.DELIVERY_RECORD),
        (r"affectation",DocumentClass.ALLOCATION_RESPONSE),(r"paiement|virement|reçu de règlement",DocumentClass.PAYMENT_RECORD),
        (r"contrat|convention",DocumentClass.CONTRACT),(r"déclaration|declaration",DocumentClass.DECLARATION),
        (r"avoir",DocumentClass.CREDIT_NOTE),(r"facture",DocumentClass.INVOICE)):
        if re.search(words,title):
            return kind
    return DocumentClass.OTHER_OR_UNKNOWN


def extract_labelled(text):
    if text.status not in ("OK","PARTIAL"):
        return None
    candidates = []
    kind = classify_native(text)
    for field,label in LABELS.items():
        matches = [(page.page,m.group(1).strip()) for page in text.pages
            for m in re.finditer(r"(?im)^\s*(?:"+label+r")\s*:\s*([^\r\n]+)",page.text)]
        if not matches:
            continue
        page,raw = matches[0]
        normalized = raw
        ambiguity = ["CONFLICTING_SOURCE_FIELDS"] if len({v for _,v in matches}) > 1 else []
        if field.endswith("_millimes") or field in ("line_quantity","tax_rate"):
            value = re.sub(r"\s*(DT|TND|EUR|USD|%)\s*$","",raw,flags=re.I).replace(" ","").replace("\u00a0","").replace(",",".")
            try:
                number = Decimal(value)
                if not number.is_finite():
                    raise InvalidOperation
                if field.endswith("_millimes"):
                    number *= 1000
                    if number != number.to_integral_value():
                        raise InvalidOperation
                normalized = str(int(number)) if field.endswith("_millimes") else str(number)
            except InvalidOperation:
                ambiguity.append("UNPARSEABLE_NUMBER")
        name = "invoice_number" if field == "reference" and kind is DocumentClass.INVOICE else field
        candidates.append(CandidateField(field_name=name,raw_value=raw,normalized_value=normalized,
            evidence_refs=(EvidenceRef(document_id=text.document_id,page=page,exact_text=raw,field_name=name),),
            ambiguities=tuple(ambiguity)))
    if not candidates:
        return None
    digest=hashlib.sha256("\n".join(p.text for p in text.pages).encode()).hexdigest()[:12]
    result=ExtractionProposal(proposal_id=f"LABEL-{text.document_id}-{digest}",document_id=text.document_id,
        candidates=tuple(candidates),mode=Mode.TEMPLATE,prompt_version="labelled-native-1")
    return validate_extraction_proposal(text,result)
