"""Compare two documented perspectives of one invoice without double counting it."""

from __future__ import annotations

from decimal import Decimal

from boussla.contracts import (
    AcquisitionChannel,
    EvidenceRef,
    Finding,
    FindingFamily,
    FindingStatus,
    Perspective,
    TransactionInputs,
)

CALCULATION_VERSION = "V4-INVOICE-1"
CONFIRMED_FIELDS = {"CONFIRMED", "FIXTURE_FIELDS_KNOWN"}


def _tax_id(value: str | None) -> str | None:
    """Remove display separators only; this is not official ID validation."""
    return "".join(char for char in value.upper() if char.isalnum()) if value else None


def _finding(
    inputs: TransactionInputs,
    status: FindingStatus,
    reason: str,
    refs: tuple[EvidenceRef, ...] = (),
    *,
    severity: str | None = None,
    basis: str | None = None,
    difference: int | None = None,
    quantity_difference: str | None = None,
    unit: str | None = None,
    missing: tuple[str, ...] = (),
) -> Finding:
    return Finding(
        finding_id=f"{inputs.transaction.transaction_id}:COUNTERPARTY:v{inputs.case_version}",
        case_id=inputs.case_id,
        company_id=inputs.company_id,
        transaction_id=inputs.transaction.transaction_id,
        family=FindingFamily.COUNTERPARTY,
        status=status,
        severity=severity,
        financial_basis=basis,
        observed_difference_millimes=difference,
        quantity_difference=quantity_difference,
        unit=unit,
        evidence_refs=refs,
        missing_evidence_types=missing,
        reason_code=reason,
        calculation_version=("V4-INVOICE-2" if any(len(o.lines) > 1 for o in inputs.invoice_observations) else CALCULATION_VERSION),
        case_version=inputs.case_version,
    )


def compare_invoice_observations(inputs: TransactionInputs) -> Finding:
    """Return one counterparty finding for the scoped economic transaction.

    Only a confirmed buyer view and a separately sourced seller view are
    comparable. Ambiguous linkage or provenance stays insufficient rather
    than becoming a financial discrepancy.
    """
    transaction = inputs.transaction
    selected = [
        observation for observation in inputs.invoice_observations
        if observation.observation_id in transaction.invoice_observation_ids
        and observation.transaction_id == transaction.transaction_id
        and observation.available_at <= inputs.as_of
    ]
    buyers = [o for o in selected if o.perspective is Perspective.BUYER_RECEIVED]
    sellers = [o for o in selected if o.perspective is Perspective.SELLER_ISSUED]
    if len(buyers) != 1 or len(sellers) != 1:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INVOICE_PAIR_UNAVAILABLE_OR_AMBIGUOUS",
                        missing=("UNAMBIGUOUS_BUYER_AND_SELLER_VIEWS",))

    buyer, seller = buyers[0], sellers[0]
    refs = (EvidenceRef(document_id=buyer.document_id, field_name="invoice"),
            EvidenceRef(document_id=seller.document_id, field_name="invoice"))
    documents = {document.document_id: document for document in inputs.documents}
    buyer_doc, seller_doc = documents.get(buyer.document_id), documents.get(seller.document_id)
    if buyer_doc is None or seller_doc is None:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "SOURCE_PROVENANCE_UNAVAILABLE", refs,
                        missing=("DOCUMENT_SOURCE_LINEAGE",))
    if any(
        document.case_id != inputs.case_id or document.subject_company_id != inputs.company_id
        or document.origin_group_id != observation.origin_group_id
        or document.received_at > inputs.as_of
        for document, observation in ((buyer_doc, buyer), (seller_doc, seller))
    ):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "SOURCE_SCOPE_OR_LINEAGE_MISMATCH", refs,
                        missing=("SCOPED_SOURCE_LINEAGE",))
    if (buyer.origin_group_id == seller.origin_group_id
            or seller_doc.acquisition_channel is not AcquisitionChannel.SIMULATED_COUNTERPARTY_REFERENCE):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INDEPENDENT_COUNTERPARTY_NOT_ESTABLISHED", refs,
                        missing=("INDEPENDENT_COUNTERPARTY_VIEW",))
    if buyer.transcription_status not in CONFIRMED_FIELDS or seller.transcription_status not in CONFIRMED_FIELDS:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INVOICE_FIELDS_UNCONFIRMED", refs,
                        missing=("CONFIRMED_INVOICE_FIELDS",))

    if (buyer.buyer_company_id != transaction.buyer_company_id
            or seller.buyer_company_id != transaction.buyer_company_id
            or buyer.issuer_company_id != seller.issuer_company_id
            or (transaction.seller_company_id is not None
                and (buyer.issuer_company_id != transaction.seller_company_id
                     or seller.issuer_company_id != transaction.seller_company_id))):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "WRONG_COMPANY_OR_ISSUER", refs,
                        missing=("MATCHING_TRANSACTION_IDENTITY",))
    if (not buyer.issuer_mf_raw or not seller.issuer_mf_raw
            or not buyer.buyer_mf_raw or not seller.buyer_mf_raw
            or _tax_id(buyer.issuer_mf_raw) != _tax_id(seller.issuer_mf_raw)
            or _tax_id(buyer.buyer_mf_raw) != _tax_id(seller.buyer_mf_raw)
            or buyer.invoice_number != seller.invoice_number
            or buyer.invoice_version != seller.invoice_version
            or buyer.issued_on != seller.issued_on):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INVOICE_LINKAGE_AMBIGUOUS", refs,
                        missing=("MATCHING_INVOICE_IDENTITY",))
    if buyer.currency != seller.currency:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INCOMPATIBLE_CURRENCY", refs,
                        missing=("COMMON_CURRENCY",))

    for field, basis in (("gross_millimes", "GROSS_TTC"), ("net_millimes", "NET_HT"),
                         ("tax_millimes", "TAX")):
        left, right = getattr(buyer, field), getattr(seller, field)
        if left != right:
            gap = abs(left - right)
            severity = min(Decimal(gap) / max(abs(right), 1) / Decimal("0.20"), Decimal(1))
            amount_refs = (EvidenceRef(document_id=buyer.document_id, field_name=field),
                           EvidenceRef(document_id=seller.document_id, field_name=field))
            return _finding(inputs, FindingStatus.UNRESOLVED, "INVOICE_AMOUNT_CONFLICT", amount_refs,
                            severity=str(severity), basis=basis, difference=gap)
    from boussla.reconciliation import line_pairs
    pairs = line_pairs(buyer, seller)
    if pairs is None:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "LINE_COMPARISON_UNSUPPORTED", refs,
                        missing=("UNAMBIGUOUS_MATCHED_INVOICE_LINES",))
    for buyer_line, seller_line in pairs:
        if buyer_line is None or seller_line is None:
            return _finding(inputs, FindingStatus.UNRESOLVED, "INVOICE_LINE_IDENTITY_CONFLICT", refs,
                            severity="1", basis="LINE_ITEM_OR_UNIT")
        if (not buyer_line.normalized_item_code or not seller_line.normalized_item_code
                or buyer_line.normalized_item_code != seller_line.normalized_item_code
                or buyer_line.unit != seller_line.unit):
            line_refs = (EvidenceRef(document_id=buyer.document_id, field_name="lines.item_or_unit"),
                         EvidenceRef(document_id=seller.document_id, field_name="lines.item_or_unit"))
            return _finding(inputs, FindingStatus.UNRESOLVED, "INVOICE_LINE_IDENTITY_CONFLICT", line_refs,
                            severity="1", basis="LINE_ITEM_OR_UNIT")
        if Decimal(buyer_line.quantity) != Decimal(seller_line.quantity):
            gap = abs(Decimal(buyer_line.quantity) - Decimal(seller_line.quantity))
            severity = min(gap / max(abs(Decimal(seller_line.quantity)), Decimal(1))
                           / Decimal("0.20"), Decimal(1))
            line_refs = (EvidenceRef(document_id=buyer.document_id, field_name="lines.quantity"),
                         EvidenceRef(document_id=seller.document_id, field_name="lines.quantity"))
            return _finding(inputs, FindingStatus.UNRESOLVED, "INVOICE_LINE_QUANTITY_CONFLICT", line_refs,
                            severity=str(severity), basis="LINE_QUANTITY",
                            quantity_difference=str(gap), unit=buyer_line.unit)
        for field in ("unit_price_millimes", "line_net_millimes"):
            left, right = getattr(buyer_line, field), getattr(seller_line, field)
            if left != right:
                gap = abs(left - right)
                severity = min(Decimal(gap) / max(abs(right), 1) / Decimal("0.20"), Decimal(1))
                line_refs = (EvidenceRef(document_id=buyer.document_id, field_name=f"lines.{field}"),
                             EvidenceRef(document_id=seller.document_id, field_name=f"lines.{field}"))
                return _finding(inputs, FindingStatus.UNRESOLVED, "INVOICE_LINE_AMOUNT_CONFLICT", line_refs,
                                severity=str(severity), basis=field.upper(), difference=gap)
    return _finding(inputs, FindingStatus.EXPLAINED, "INDEPENDENT_INVOICE_VIEWS_MATCH", refs,
                    severity="0")
