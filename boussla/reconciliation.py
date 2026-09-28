"""Deterministic invoice pairing with explicit missing and ambiguous states."""
from datetime import datetime
from decimal import Decimal
from boussla.contracts import AcquisitionChannel, InvoiceComparisonView, Perspective

HEADER_FIELDS = ("invoice_number", "invoice_version", "issuer_company_id", "buyer_company_id",
                 "issued_on", "net_millimes", "tax_millimes", "gross_millimes", "currency")
LINE_FIELDS = ("normalized_item_code", "item_description", "quantity", "unit", "unit_price_millimes",
               "line_net_millimes", "tax_rate")


def line_pairs(buyer, seller):
    if len(buyer.lines) == len(seller.lines) == 1:
        return [(buyer.lines[0], seller.lines[0])]
    if not buyer.lines or not seller.lines:
        return None
    left = {line.normalized_item_code: line for line in buyer.lines}
    right = {line.normalized_item_code: line for line in seller.lines}
    if None in left or None in right or len(left) != len(buyer.lines) or len(right) != len(seller.lines):
        return None
    return [(left.get(key), right.get(key)) for key in sorted(left.keys() | right.keys())]


def compare_transaction(transaction, observations, documents, as_of: datetime):
    candidates = [o for o in observations if o.transaction_id == transaction.transaction_id
                  and o.observation_id in transaction.invoice_observation_ids and o.available_at <= as_of]
    buyers = [o for o in candidates if o.perspective is Perspective.BUYER_RECEIVED]
    sellers = [o for o in candidates if o.perspective is Perspective.SELLER_ISSUED]
    common = dict(transaction_id=transaction.transaction_id,
                  candidate_observation_ids=tuple(sorted(o.observation_id for o in candidates)),
                  rule_version="invoice-reconciliation-2", calculated_at=as_of)
    def result(state, label, status="SINGLE_OBSERVATION", **extra):
        return InvoiceComparisonView(**common,reconciliation_status=state,label_fr=label,status=status,**extra)
    if not candidates:
        return result("NON_RAPPROCHE", "Non rapproché : aucune observation admissible")
    if len(buyers) > 1 or len(sellers) > 1:
        return result("RAPPROCHEMENT_AMBIGU", "Rapprochement ambigu : plusieurs observations candidates", "AMBIGUOUS")
    buyer = buyers[0] if buyers else None
    seller = sellers[0] if sellers else None
    common.update(buyer_observation_id=buyer.observation_id if buyer else None,
                  seller_observation_id=seller.observation_id if seller else None)
    if buyer is None or seller is None:
        return result("EN_ATTENTE_DE_CONTREPARTIE", "En attente de contrepartie : absence de deuxième facture, pas une anomalie")
    docs = {d.document_id: d for d in documents}
    bd, sd = docs.get(buyer.document_id), docs.get(seller.document_id)
    independent = (bd is not None and sd is not None and bd.case_id == sd.case_id
                   and bd.subject_company_id == sd.subject_company_id == transaction.buyer_company_id
                   and bd.received_at <= as_of and sd.received_at <= as_of
                   and bd.origin_group_id == buyer.origin_group_id
                   and sd.origin_group_id == seller.origin_group_id
                   and buyer.origin_group_id != seller.origin_group_id
                   and sd.acquisition_channel is AcquisitionChannel.SIMULATED_COUNTERPARTY_REFERENCE)
    confirmed = all(o.transcription_status in {"CONFIRMED", "FIXTURE_FIELDS_KNOWN"} for o in (buyer,seller))
    if not independent or not confirmed:
        return result("NON_RAPPROCHE", "Non rapproché : provenance indépendante ou champs confirmés insuffisants")
    if any(not o.issuer_company_id or not o.buyer_company_id or not o.issuer_mf_raw or not o.buyer_mf_raw for o in (buyer,seller)):
        return result("NON_RAPPROCHE", "Non rapproché : identités documentaires incomplètes")
    diffs = [field for field in HEADER_FIELDS if getattr(buyer,field) != getattr(seller,field)]
    for field in ("issuer_mf_raw", "buyer_mf_raw"):
        norm = lambda value: "".join(c for c in (value or "").upper() if c.isalnum())
        if norm(getattr(buyer,field)) != norm(getattr(seller,field)):
            diffs.append(field)
    pairs = line_pairs(buyer,seller)
    if pairs is None:
        return result("RAPPROCHEMENT_AMBIGU", "Rapprochement ambigu : correspondance des lignes indéterminée", "AMBIGUOUS", difference_fields=tuple(diffs))
    for index, (left,right) in enumerate(pairs):
        prefix = "line" if len(pairs) == 1 else f"lines[{index}]"
        if left is None or right is None:
            diffs.append(prefix)
            continue
        for field in LINE_FIELDS:
            a,b = getattr(left,field),getattr(right,field)
            if field in ("quantity","tax_rate") and a is not None and b is not None:
                a,b = Decimal(a),Decimal(b)
            if a != b:
                diffs.append(f"{prefix}.{field}")
    return result("ECART_DETECTE" if diffs else "RAPPROCHE",
                  "Écart détecté entre les observations" if diffs else "Observations rapprochées",
                  "DIFFERENCES" if diffs else "CONCORDANT", difference_fields=tuple(diffs))
