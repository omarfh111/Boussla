"""Finite quantity sensitivity grid and unaccepted candidate reallocation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from boussla.checks.quantities import compare_quantity_allocations
from boussla.contracts import (
    AllocationStatus, AllocationTarget, BaselineKind, FindingStatus,
    Perspective, Scenario, TransactionInputs,
)


def _decimal(value: object) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("scenario quantities and margins must be decimal strings")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal scenario input") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("scenario inputs must be finite and non-negative")
    return number


def _text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _scope(inputs: TransactionInputs):
    transaction = inputs.transaction
    invoices = [o for o in inputs.invoice_observations
                if o.perspective is Perspective.BUYER_RECEIVED
                and o.observation_id in transaction.invoice_observation_ids
                and o.transaction_id == transaction.transaction_id
                and o.available_at <= inputs.as_of]
    if len(invoices) != 1 or len(invoices[0].lines) != 1:
        return None
    line = invoices[0].lines[0]
    if any(a.transaction_id == transaction.transaction_id and a.status is AllocationStatus.ACCEPTED
           and a.target_type is not AllocationTarget.PROJECT for a in inputs.allocations):
        # Warehouse/return transfers need their own conservation semantics.
        return None
    allocations = [a for a in inputs.allocations
                   if a.transaction_id == transaction.transaction_id
                   and a.status is AllocationStatus.ACCEPTED
                   and a.target_type is AllocationTarget.PROJECT
                   and a.line_id == line.line_id and a.unit == line.unit
                   and a.effective_on <= inputs.as_of.date()]
    if not allocations:
        return None
    references = {}
    for project_id in {a.target_project_id for a in allocations}:
        matches = [r for r in inputs.quantity_references
                   if r.company_id == inputs.company_id and r.project_id == project_id
                   and r.item_code == line.normalized_item_code and r.unit == line.unit
                   and r.baseline_kind is BaselineKind.APPROVED_PROCUREMENT_ALLOCATION
                   and r.acceptance_status in {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
                   and all(r.valid_from <= a.effective_on and
                           (r.valid_to is None or a.effective_on <= r.valid_to)
                           for a in allocations if a.target_project_id == project_id)]
        if len(matches) != 1:
            return None
        references[project_id] = matches[0]
    return line, allocations, references


def run_scenarios(inputs: TransactionInputs, config: dict) -> list[Scenario]:
    """Evaluate an explicit margin grid and optional candidate; never mutate inputs."""
    margins = config.get("quantity_margins", ("0", "0.10"))
    if not isinstance(margins, (list, tuple)) or not 1 <= len(margins) <= 5:
        raise ValueError("quantity_margins must contain one to five decimal strings")
    parsed_margins = [_decimal(margin) for margin in margins]
    if len(set(parsed_margins)) != len(parsed_margins):
        raise ValueError("duplicate scenario margin")
    finding = compare_quantity_allocations(inputs)
    scoped = _scope(inputs) if finding.status is not FindingStatus.INSUFFICIENT else None
    result = []
    for label, margin in zip(margins, parsed_margins):
        if scoped is None:
            outputs = {"status": "NOT_COMPARABLE"}
        else:
            line, allocations, references = scoped
            residual = sum((max(sum((Decimal(a.quantity) for a in allocations
                                     if a.target_project_id == project_id), Decimal(0))
                                - Decimal(reference.quantity) * (Decimal(1) + margin), Decimal(0))
                            for project_id, reference in references.items()), Decimal(0))
            outputs = {"status": "HYPOTHETICAL", "residual_units": _text(residual), "unit": line.unit}
        result.append(Scenario(
            scenario_id=f"{inputs.transaction.transaction_id}:MARGIN:{label}:v{inputs.case_version}",
            label=f"Marge hypothétique {margin * 100}% (non autorisée)",
            assumption_ids=(f"HYPOTHETICAL_MARGIN_{label}",),
            inputs={"quantity_margin": label}, outputs=outputs,
            evidence_refs=finding.evidence_refs,
        ))

    candidate = config.get("candidate_reallocation")
    if candidate is not None:
        if not isinstance(candidate, dict) or not candidate:
            raise ValueError("candidate_reallocation must map project IDs to decimal strings")
        amounts = {str(project_id): _decimal(quantity) for project_id, quantity in candidate.items()}
        outputs = {"status": "NOT_COMPARABLE"}
        if scoped is not None:
            line, accepted_allocations, references = scoped
            # The candidate can include a second project with its own accepted
            # reference, even though no allocation has yet been accepted there.
            for project_id in amounts:
                if project_id not in references:
                    matches = [r for r in inputs.quantity_references
                               if r.company_id == inputs.company_id and r.project_id == project_id
                               and r.item_code == line.normalized_item_code and r.unit == line.unit
                               and r.baseline_kind is BaselineKind.APPROVED_PROCUREMENT_ALLOCATION
                               and r.acceptance_status in {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
                               and r.accepted_by and r.source_refs
                               and r.valid_from <= inputs.as_of.date()
                               and (r.valid_to is None or inputs.as_of.date() <= r.valid_to)]
                    if len(matches) == 1:
                        references[project_id] = matches[0]
            received = sum((Decimal(d.quantity) for d in inputs.deliveries
                            if d.transaction_id == inputs.transaction.transaction_id
                            and d.item_code == line.normalized_item_code and d.unit == line.unit
                            and d.status in {"ACCEPTED", "ACCEPTED_SYNTHETIC_FIXTURE"}
                            and d.received_at <= inputs.as_of.date()), Decimal(0))
            budget = min(Decimal(line.quantity), received)
            candidate_total = sum(amounts.values(), Decimal(0))
            current_total = sum((Decimal(a.quantity) for a in accepted_allocations), Decimal(0))
            if candidate_total > budget:
                outputs = {"status": "INVALID_BUDGET", "budget_units": _text(budget), "unit": line.unit}
            elif candidate_total != current_total:
                outputs = {"status": "INCOMPLETE_REALLOCATION", "current_units": _text(current_total),
                           "candidate_units": _text(candidate_total), "unit": line.unit}
            elif not set(amounts) <= references.keys():
                outputs = {"status": "UNKNOWN_PROJECT_REFERENCE", "unit": line.unit}
            else:
                residual = sum((max(quantity - Decimal(references[project_id].quantity), Decimal(0))
                                for project_id, quantity in amounts.items()), Decimal(0))
                outputs = {"status": "CANDIDATE_UNACCEPTED", "residual_units": _text(residual),
                           "unit": line.unit}
        result.append(Scenario(
            scenario_id=f"{inputs.transaction.transaction_id}:CANDIDATE:v{inputs.case_version}",
            label="Réaffectation proposée, non acceptée",
            assumption_ids=("CANDIDATE_ALLOCATION_UNACCEPTED",),
            inputs={project_id: str(quantity) for project_id, quantity in amounts.items()},
            outputs=outputs, evidence_refs=finding.evidence_refs,
        ))
    return result
