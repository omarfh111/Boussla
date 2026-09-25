"""Reconcile documented cash allocations without treating an invoice as cash."""

from __future__ import annotations

from boussla.contracts import (
    EvidenceRef, Finding, FindingFamily, FindingStatus, PaymentStatus,
    Perspective, TransactionInputs,
)

CALCULATION_VERSION = "V4-SETTLEMENT-1"
ACCEPTED_MAPPING_STATUSES = {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
CONFIRMED_FIELDS = {"CONFIRMED", "FIXTURE_FIELDS_KNOWN"}


def _finding(inputs: TransactionInputs, status: FindingStatus, reason: str,
             refs: tuple[EvidenceRef, ...] = (), *, missing: tuple[str, ...] = ()) -> Finding:
    return Finding(
        finding_id=f"{inputs.transaction.transaction_id}:SETTLEMENT:v{inputs.case_version}",
        case_id=inputs.case_id, company_id=inputs.company_id,
        transaction_id=inputs.transaction.transaction_id,
        family=FindingFamily.SETTLEMENT, status=status,
        severity="0" if status is FindingStatus.EXPLAINED else None,
        financial_basis="GROSS_TTC_NET_OF_ACCEPTED_ADJUSTMENTS" if status is FindingStatus.EXPLAINED else None,
        evidence_refs=refs, missing_evidence_types=missing, reason_code=reason,
        calculation_version=CALCULATION_VERSION, case_version=inputs.case_version,
    )


def reconcile_settlements(inputs: TransactionInputs) -> Finding:
    """Confirm an exact documented settlement, otherwise abstain safely.

    The current shared contract has no due schedule or complete-settlement
    coverage field. A residual may be an ordinary installment, so it cannot
    produce an adverse SETTLEMENT finding from these inputs alone.
    """
    transaction = inputs.transaction
    invoices = [
        observation for observation in inputs.invoice_observations
        if observation.perspective is Perspective.BUYER_RECEIVED
        and observation.observation_id in transaction.invoice_observation_ids
        and observation.transaction_id == transaction.transaction_id
        and observation.available_at <= inputs.as_of
        and observation.transcription_status in CONFIRMED_FIELDS
        and observation.buyer_company_id == transaction.buyer_company_id
    ]
    if len(invoices) != 1:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "PAYABLE_INVOICE_UNAVAILABLE_OR_AMBIGUOUS",
                        missing=("ONE_CONFIRMED_PAYABLE_INVOICE",))
    invoice = invoices[0]
    refs = [EvidenceRef(document_id=invoice.document_id, field_name="gross_millimes")]
    adjustments = [a for a in inputs.settlement_adjustments if a.transaction_id == transaction.transaction_id]
    if any(a.status.value != "ACCEPTED" or a.accepted_by is None or not a.supporting_refs
           for a in adjustments):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "UNACCEPTED_SETTLEMENT_ADJUSTMENT",
                        tuple(refs), missing=("ACCEPTED_ADJUSTMENT_SUPPORT",))
    payable = invoice.gross_millimes + sum(a.signed_millimes for a in adjustments)
    if payable < 0:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "INVALID_NET_PAYABLE", tuple(refs),
                        missing=("VALID_NET_PAYABLE",))
    refs.extend(EvidenceRef(source_record_id=ref) for a in adjustments for ref in a.supporting_refs)

    allocations = [a for a in inputs.payment_allocations if a.transaction_id == transaction.transaction_id
                   and a.accepted_at <= inputs.as_of]
    if not allocations:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "NO_SETTLED_ALLOCATION", tuple(refs),
                        missing=("SETTLED_PAYMENT_ALLOCATION",))
    if len({a.payment_id for a in allocations}) != len(allocations):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "DUPLICATE_PAYMENT_ALLOCATION", tuple(refs),
                        missing=("UNAMBIGUOUS_PAYMENT_ALLOCATION",))
    payments = {p.payment_id: p for p in inputs.payments}
    mappings = {m.mapping_id: m for m in inputs.identity_mappings}
    total = 0
    for allocation in allocations:
        payment = payments.get(allocation.payment_id)
        if (payment is None or payment.status is not PaymentStatus.SETTLED
                or payment.available_at > inputs.as_of or payment.occurred_at > inputs.as_of
                or payment.currency != invoice.currency or allocation.allocated_millimes > payment.amount_millimes
                or payment.payer_company_id != transaction.buyer_company_id
                or payment.payee_company_id != transaction.seller_company_id):
            return _finding(inputs, FindingStatus.INSUFFICIENT, "INCOMPARABLE_PAYMENT", tuple(refs),
                            missing=("COMPARABLE_SETTLED_PAYMENT",))
        payer = mappings.get(payment.payer_mapping_ref)
        payee = mappings.get(payment.payee_mapping_ref)
        if (payer is None or payee is None
                or payer.company_id != transaction.buyer_company_id
                or payee.company_id != transaction.seller_company_id
                or payer.source_record_id != payment.source_record_id
                or payee.source_record_id != payment.source_record_id
                or payer.status not in ACCEPTED_MAPPING_STATUSES
                or payee.status not in ACCEPTED_MAPPING_STATUSES
                or payer.verified_by is None or payee.verified_by is None):
            return _finding(inputs, FindingStatus.INSUFFICIENT, "PAYMENT_IDENTITY_UNVERIFIED", tuple(refs),
                            missing=("ACCEPTED_PAYER_AND_PAYEE_MAPPING",))
        total += allocation.allocated_millimes
        refs.append(EvidenceRef(source_record_id=payment.source_record_id, field_name="amount_millimes"))
    if total != payable:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "PARTIAL_OR_UNEXPLAINED_SETTLEMENT_STAGE",
                        tuple(refs), missing=("DUE_SCHEDULE_AND_COMPLETE_SETTLEMENT_COVERAGE",))
    return _finding(inputs, FindingStatus.EXPLAINED, "DOCUMENTED_SETTLEMENT_MATCHES_PAYABLE", tuple(refs))
