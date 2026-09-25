"""Compare accepted allocation claims with scoped procurement references."""

from __future__ import annotations

from decimal import Decimal

from boussla.contracts import (
    AllocationStatus, AllocationTarget, BaselineKind, EvidenceRef, Finding,
    FindingFamily, FindingStatus, Perspective, TransactionInputs,
)

CALCULATION_VERSION = "V4-QUANTITY-1"
ACCEPTED_REFERENCE_STATUSES = {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
ACCEPTED_DELIVERY_STATUSES = {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
CONFIRMED_FIELDS = {"CONFIRMED", "FIXTURE_FIELDS_KNOWN"}


def _finding(inputs: TransactionInputs, status: FindingStatus, reason: str,
             refs: tuple[EvidenceRef, ...] = (), *, severity: str | None = None,
             difference: str | None = None, unit: str | None = None,
             missing: tuple[str, ...] = ()) -> Finding:
    return Finding(
        finding_id=f"{inputs.transaction.transaction_id}:QUANTITY:v{inputs.case_version}",
        case_id=inputs.case_id, company_id=inputs.company_id,
        transaction_id=inputs.transaction.transaction_id,
        family=FindingFamily.QUANTITY, status=status, severity=severity,
        quantity_difference=difference, unit=unit, evidence_refs=refs,
        missing_evidence_types=missing, reason_code=reason,
        calculation_version=CALCULATION_VERSION, case_version=inputs.case_version,
    )


def compare_quantity_allocations(inputs: TransactionInputs) -> Finding:
    """Find project allocation excess only when item, unit, date and receipt align."""
    transaction = inputs.transaction
    invoices = [o for o in inputs.invoice_observations
                if o.perspective is Perspective.BUYER_RECEIVED
                and o.observation_id in transaction.invoice_observation_ids
                and o.transaction_id == transaction.transaction_id
                and o.buyer_company_id == transaction.buyer_company_id
                and o.available_at <= inputs.as_of
                and o.transcription_status in CONFIRMED_FIELDS]
    if len(invoices) != 1 or len(invoices[0].lines) != 1:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "MATERIAL_LINE_UNAVAILABLE_OR_AMBIGUOUS",
                        missing=("ONE_CONFIRMED_MATERIAL_LINE",))
    invoice, line = invoices[0], invoices[0].lines[0]
    if not line.normalized_item_code:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ITEM_IDENTITY_UNKNOWN",
                        missing=("NORMALIZED_ITEM_CODE",))
    refs = [EvidenceRef(document_id=invoice.document_id, field_name="lines.quantity")]
    accepted = [a for a in inputs.allocations
                if a.transaction_id == transaction.transaction_id and a.status is AllocationStatus.ACCEPTED
                and a.effective_on <= inputs.as_of.date()]
    if not accepted:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ACCEPTED_ALLOCATION_UNAVAILABLE",
                        tuple(refs), missing=("ACCEPTED_PROJECT_ALLOCATION",))
    if (len({a.allocation_id for a in accepted}) != len(accepted)
            or any(a.line_id != line.line_id or a.unit != line.unit or Decimal(a.quantity) < 0
                   for a in accepted)):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ALLOCATION_ID_OR_UNIT_AMBIGUOUS",
                        tuple(refs), missing=("UNIQUE_SAME_UNIT_ALLOCATIONS",))
    if any(a.fact_kind in {"USER_ESTIMATE", "CONSUMPTION_ESTIMATE"} for a in accepted):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ESTIMATE_ONLY_ALLOCATION",
                        tuple(refs), missing=("ACCEPTED_PROCUREMENT_ASSIGNMENT",))
    deliveries = [d for d in inputs.deliveries if d.transaction_id == transaction.transaction_id
                  and d.item_code == line.normalized_item_code and d.unit == line.unit
                  and d.status in ACCEPTED_DELIVERY_STATUSES and d.received_at <= inputs.as_of.date()]
    if not deliveries:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ELIGIBLE_RECEIPT_UNAVAILABLE",
                        tuple(refs), missing=("ACCEPTED_SAME_ITEM_DELIVERY",))
    total_assigned = sum((Decimal(a.quantity) for a in accepted), Decimal(0))
    purchased = Decimal(line.quantity)
    received = sum((Decimal(d.quantity) for d in deliveries), Decimal(0))
    if total_assigned > purchased or total_assigned > received or received > purchased:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "ALLOCATION_CONSERVATION_FAILED",
                        tuple(refs), missing=("BUDGET_VALID_ALLOCATION_LEDGER",))
    refs.extend(EvidenceRef(source_record_id=source) for d in deliveries for source in d.source_refs)

    project_allocations = [a for a in accepted if a.target_type is AllocationTarget.PROJECT]
    if not project_allocations or any(a.target_project_id is None for a in project_allocations):
        return _finding(inputs, FindingStatus.INSUFFICIENT, "PROJECT_ASSIGNMENT_UNAVAILABLE",
                        tuple(refs), missing=("SCOPED_PROJECT_ASSIGNMENT",))
    project_ids = {a.target_project_id for a in project_allocations}
    if transaction.project_id and transaction.project_id not in project_ids:
        return _finding(inputs, FindingStatus.INSUFFICIENT, "PRIMARY_PROJECT_UNASSIGNED",
                        tuple(refs), missing=("PRIMARY_PROJECT_ALLOCATION",))
    excess = Decimal(0)
    max_severity = Decimal(0)
    for project_id in sorted(project_ids):
        allocations = [a for a in project_allocations if a.target_project_id == project_id]
        candidates = [r for r in inputs.quantity_references
                      if r.company_id == inputs.company_id and r.project_id == project_id
                      and r.item_code == line.normalized_item_code and r.unit == line.unit
                      and r.baseline_kind is BaselineKind.APPROVED_PROCUREMENT_ALLOCATION
                      and r.acceptance_status in ACCEPTED_REFERENCE_STATUSES and r.accepted_by
                      and all(r.valid_from <= a.effective_on and
                              (r.valid_to is None or a.effective_on <= r.valid_to)
                              for a in allocations)]
        if len(candidates) != 1 or not candidates[0].source_refs:
            return _finding(inputs, FindingStatus.INSUFFICIENT, "PROCUREMENT_BASELINE_UNAVAILABLE",
                            tuple(refs), missing=("ACCEPTED_SAME_SCOPE_PROCUREMENT_REFERENCE",))
        reference = candidates[0]
        refs.extend(EvidenceRef(source_record_id=source) for source in reference.source_refs)
        refs.extend(EvidenceRef(source_record_id=source) for a in allocations for source in a.source_refs)
        assigned = sum((Decimal(a.quantity) for a in allocations), Decimal(0))
        limit = Decimal(reference.quantity)
        if limit < 0:
            return _finding(inputs, FindingStatus.INSUFFICIENT, "INVALID_PROCUREMENT_LIMIT",
                            tuple(refs), missing=("NONNEGATIVE_PROCUREMENT_LIMIT",))
        gap = max(assigned - limit, Decimal(0))
        excess += gap
        if gap:
            max_severity = max(max_severity, min(gap / max(limit, Decimal(1)) / Decimal("0.50"), Decimal(1)))
    if excess:
        return _finding(inputs, FindingStatus.UNRESOLVED, "PROJECT_ALLOCATION_EXCEEDS_REFERENCE",
                        tuple(refs), severity=str(max_severity), difference=str(excess), unit=line.unit)
    return _finding(inputs, FindingStatus.EXPLAINED, "PROJECT_ALLOCATIONS_WITHIN_REFERENCES",
                    tuple(refs), severity="0", difference="0", unit=line.unit)
