"""INTERIM checks engine — lane A glue, to be replaced by lane B's ``boussla.checks``.

Composes the pack's tested reference functions (``docs/build_lock/reference/
core.py``: weights 35/25/40, 20%/50% severity scales, settlement residual,
quantity excess, allocation budget, scenarios) behind ``ChecksEngine`` so the
real service can run end to end before B merges. Every finding carries
``calculation_version=INTERIM_CALC_VERSION`` so it is never mistaken for B's
reviewed checks. Deliberately conservative: anything the reference does not
support becomes ``INSUFFICIENT`` rather than an adverse finding.

Pure: no clock, network, model, randomness or global state.
"""
from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from functools import lru_cache
from types import ModuleType

from boussla.config import REPO_ROOT
from boussla.contracts import (
    AllocationStatus, AllocationTarget, BaselineKind, EvidenceRef, Finding, FindingFamily, FindingStatus,
    Hypothesis, HypothesisStatus, InvoiceObservation, PaymentStatus, Perspective, Scenario, ScoreResult,
    TransactionInputs,
)

INTERIM_CALC_VERSION = "INTERIM-A-GLUE+PACK-REFERENCE-CONTEXT_RULES_V4_1"
AMOUNT_FULL_SEVERITY_RATIO = Decimal("0.20")
DEFAULT_MARGINS = ("0.00", "0.10")


@lru_cache(maxsize=1)
def _core() -> ModuleType:
    path = REPO_ROOT / "docs" / "build_lock" / "reference" / "core.py"
    spec = importlib.util.spec_from_file_location("boussla_pack_reference_core", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations via sys.modules
    spec.loader.exec_module(module)
    return module


def _amount_severity(gap: int, reference: int) -> str:
    sev = min(Decimal(abs(gap)) / Decimal(max(reference, 1)) / AMOUNT_FULL_SEVERITY_RATIO, Decimal(1))
    return str(sev)


def _obs_ref(o: InvoiceObservation, field: str | None = None) -> EvidenceRef:
    return EvidenceRef(document_id=o.document_id, source_record_id=o.observation_id, field_name=field)


class InterimChecks:
    """``ChecksEngine`` implementation (interim)."""

    calculation_version = INTERIM_CALC_VERSION

    # ------------------------------------------------------------ findings
    def evaluate_transaction(self, inputs: TransactionInputs) -> list[Finding]:
        return [self._counterparty(inputs), self._settlement(inputs), self._quantity(inputs)]

    def _finding(self, inputs: TransactionInputs, family: FindingFamily, status: FindingStatus, **kw) -> Finding:
        tx = inputs.transaction.transaction_id
        return Finding(finding_id=f"F-{tx}-{family.value}", case_id=inputs.case_id, company_id=inputs.company_id,
                       transaction_id=tx, family=family, status=status, calculation_version=INTERIM_CALC_VERSION,
                       case_version=inputs.case_version, **kw)

    def _observations(self, inputs: TransactionInputs) -> list[InvoiceObservation]:
        ids = set(inputs.transaction.invoice_observation_ids)
        return [o for o in inputs.invoice_observations if o.observation_id in ids]

    def _counterparty(self, inputs: TransactionInputs) -> Finding:
        fam = FindingFamily.COUNTERPARTY
        obs = self._observations(inputs)
        buyer = [o for o in obs if o.perspective is Perspective.BUYER_RECEIVED]
        seller = [o for o in obs if o.perspective is Perspective.SELLER_ISSUED]
        if not buyer or not seller:
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="COUNTERPART_RECORD_MISSING",
                                 missing_evidence_types=("SELLER_RECORD",), evidence_refs=tuple(_obs_ref(o) for o in obs))
        b, s = buyer[0], seller[0]
        refs = (_obs_ref(b), _obs_ref(s))
        if _core().corroboration_status([b.origin_group_id, s.origin_group_id]) != "DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY":
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="COMMON_ORIGIN_NOT_INDEPENDENT",
                                 missing_evidence_types=("INDEPENDENT_SELLER_RECORD",), evidence_refs=refs)
        if b.currency != s.currency:
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="INCOMPATIBLE_BASIS", evidence_refs=refs)
        identity = ("issuer_company_id", "buyer_company_id", "invoice_number", "invoice_version", "issued_on")
        mismatched = [f for f in identity if getattr(b, f) != getattr(s, f)]
        if mismatched:
            return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity="1", reason_code="IDENTIFIER_MISMATCH",
                                 evidence_refs=tuple(_obs_ref(o, f) for o in (b, s) for f in mismatched))
        gaps = {f: getattr(s, f) - getattr(b, f) for f in ("net_millimes", "tax_millimes", "gross_millimes")}
        b_lines = sorted((ln.normalized_item_code, ln.quantity, ln.unit, ln.line_net_millimes) for ln in b.lines)
        s_lines = sorted((ln.normalized_item_code, ln.quantity, ln.unit, ln.line_net_millimes) for ln in s.lines)
        if any(gaps.values()):
            worst = max(gaps, key=lambda k: abs(gaps[k]))
            return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity=_amount_severity(gaps[worst], b.gross_millimes),
                                 financial_basis=worst.upper(), observed_difference_millimes=gaps[worst],
                                 reason_code="AMOUNT_MISMATCH", evidence_refs=refs)
        if b_lines != s_lines:
            return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity="1", reason_code="LINE_MISMATCH", evidence_refs=refs)
        return self._finding(inputs, fam, FindingStatus.EXPLAINED, severity="0", observed_difference_millimes=0,
                             reason_code="OBSERVATIONS_AGREE_DISTINCT_ORIGINS", evidence_refs=refs)

    def _settlement(self, inputs: TransactionInputs) -> Finding:
        fam = FindingFamily.SETTLEMENT
        tx = inputs.transaction
        buyer = [o for o in self._observations(inputs) if o.perspective is Perspective.BUYER_RECEIVED]
        allocs = [pa for pa in inputs.payment_allocations if pa.transaction_id == tx.transaction_id]
        payments = {p.payment_id: p for p in inputs.payments}
        refs = tuple(EvidenceRef(source_record_id=payments[pa.payment_id].source_record_id)
                     for pa in allocs if pa.payment_id in payments)
        if not buyer or not allocs:
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="NO_SETTLEMENT_RECORD",
                                 missing_evidence_types=("PAYMENT_RECORD",), evidence_refs=refs)
        payable = buyer[0].gross_millimes
        mappings = {m.mapping_id: m for m in inputs.identity_mappings if m.status.startswith("ACCEPTED")}
        mapping_ok, comparable = True, True
        rows = []
        for pa in allocs:
            p = payments.get(pa.payment_id)
            if p is None:
                return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="UNKNOWN_PAYMENT", evidence_refs=refs)
            payer, payee = mappings.get(p.payer_mapping_ref or ""), mappings.get(p.payee_mapping_ref or "")
            mapping_ok &= bool(payer and payee and payer.company_id == tx.buyer_company_id
                               and payee.company_id == tx.seller_company_id)
            comparable &= p.currency == buyer[0].currency
            rows.append({"allocation_id": f"{pa.payment_id}:{pa.transaction_id}",
                         "allocated_millimes": pa.allocated_millimes, "status": p.status.value})
        # Allocations cannot exceed a payment's settled amount.
        for pid in {pa.payment_id for pa in allocs}:
            p = payments[pid]
            total = sum(x.allocated_millimes for x in inputs.payment_allocations if x.payment_id == pid)
            if p.status is PaymentStatus.SETTLED and total > p.amount_millimes:
                return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity="1",
                                     reason_code="ALLOCATION_EXCEEDS_SETTLED_PAYMENT", evidence_refs=refs)
        res = _core().settlement_residual(payable, rows, mapping_confirmed=mapping_ok,
                                          comparable_terms=comparable, source_complete=True)
        if res["status"] != "COMPARABLE":
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT,
                                 reason_code="UNKNOWN_IDENTITY_MAPPING" if not mapping_ok else "INCOMPATIBLE_BASIS",
                                 missing_evidence_types=("IDENTITY_MAPPING",) if not mapping_ok else (), evidence_refs=refs)
        residual = res["residual_millimes"]
        common = dict(financial_basis="GROSS_PAYABLE_VS_SETTLED", observed_difference_millimes=residual, evidence_refs=refs)
        if residual == 0:
            return self._finding(inputs, fam, FindingStatus.EXPLAINED, severity="0", reason_code="SETTLED_MATCHES_PAYABLE", **common)
        if residual > 0:  # part payment: terms/due dates unknown in P0 -> abstain, no adverse finding
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="PARTIAL_SETTLEMENT_TERMS_UNKNOWN",
                                 missing_evidence_types=("SETTLEMENT_TERMS",), **common)
        return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity=_amount_severity(residual, payable),
                             reason_code="SETTLED_EXCEEDS_PAYABLE", **common)

    def _quantity_comparisons(self, inputs: TransactionInputs) -> list[dict]:
        """Per (line, project) comparison inputs against accepted procurement references."""
        out = []
        buyer = [o for o in self._observations(inputs) if o.perspective is Perspective.BUYER_RECEIVED]
        lines = {ln.line_id: ln for o in buyer for ln in o.lines}
        accepted = [a for a in inputs.allocations
                    if a.transaction_id == inputs.transaction.transaction_id and a.status is AllocationStatus.ACCEPTED]
        by_target: dict[tuple[str, str], list] = {}
        for a in accepted:
            if a.target_type is AllocationTarget.PROJECT and a.target_project_id:
                by_target.setdefault((a.line_id, a.target_project_id), []).append(a)
        for (line_id, project_id), allocs in sorted(by_target.items()):
            line = lines.get(line_id)
            assigned = sum((Decimal(a.quantity) for a in allocs), Decimal(0))
            refs = [r for r in inputs.quantity_references
                    if r.company_id == inputs.company_id and r.project_id == project_id
                    and line is not None and r.item_code == line.normalized_item_code]
            ref = next((r for r in refs if r.baseline_kind is BaselineKind.APPROVED_PROCUREMENT_ALLOCATION), refs[0] if refs else None)
            units_match = bool(ref and line and ref.unit == line.unit and all(a.unit == ref.unit for a in allocs))
            scope_match = bool(ref and all(ref.valid_from <= a.effective_on and (ref.valid_to is None or a.effective_on <= ref.valid_to)
                                           for a in allocs))
            result = _core().quantity_excess(
                str(assigned), ref.quantity if ref else None, baseline_kind=ref.baseline_kind.value if ref else "",
                reference_accepted=bool(ref and ref.acceptance_status.startswith("ACCEPTED")),
                units_match=units_match, scope_match=scope_match)
            out.append({"line": line, "project_id": project_id, "assigned": assigned, "reference": ref,
                        "allocations": allocs, "result": result})
        return out

    def _quantity(self, inputs: TransactionInputs) -> Finding:
        fam = FindingFamily.QUANTITY
        comps = self._quantity_comparisons(inputs)
        if not comps:
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="NO_ACCEPTED_PROJECT_ALLOCATION",
                                 missing_evidence_types=("ALLOCATION_REFERENCE",))
        # Budget: accepted allocations of one line cannot exceed its invoiced quantity.
        for line_id in {c["line"].line_id for c in comps if c["line"]}:
            line = next(c["line"] for c in comps if c["line"] and c["line"].line_id == line_id)
            all_for_line = {a.target_project_id: a.quantity for a in inputs.allocations
                            if a.line_id == line_id and a.status is AllocationStatus.ACCEPTED}
            try:
                _core().allocation_budget(line.quantity, {k or "_": v for k, v in all_for_line.items()})
            except ValueError:
                return self._finding(inputs, fam, FindingStatus.UNRESOLVED, severity="1", unit=line.unit,
                                     reason_code="ALLOCATION_EXCEEDS_INVOICED_QUANTITY",
                                     evidence_refs=tuple(EvidenceRef(source_record_id=a.allocation_id)
                                                         for c in comps for a in c["allocations"]))
        comparable = [c for c in comps if c["result"]["status"] == "COMPARABLE"]
        refs = tuple(EvidenceRef(source_record_id=x) for c in comps
                     for x in ([c["reference"].reference_id] if c["reference"] else []) + [a.allocation_id for a in c["allocations"]])
        if not comparable:
            return self._finding(inputs, fam, FindingStatus.INSUFFICIENT, reason_code="CONTEXT_ONLY_OR_INSUFFICIENT",
                                 missing_evidence_types=("APPROVED_PROCUREMENT_ALLOCATION",), evidence_refs=refs)
        worst = max(comparable, key=lambda c: Decimal(c["result"]["severity"]))
        sev = Decimal(worst["result"]["severity"])
        return self._finding(
            inputs, fam, FindingStatus.UNRESOLVED if sev > 0 else FindingStatus.EXPLAINED, severity=str(sev),
            quantity_difference=worst["result"]["excess"], unit=worst["line"].unit if worst["line"] else None,
            reason_code=f"ASSIGNED_EXCEEDS_REFERENCE:{worst['project_id']}" if sev > 0 else "WITHIN_ACCEPTED_REFERENCES",
            missing_evidence_types=("ALLOCATION_RESPONSE",) if sev > 0 else (), evidence_refs=refs)

    # ------------------------------------------------------------ scenarios
    def run_scenarios(self, inputs: TransactionInputs, config: dict | None = None) -> list[Scenario]:
        margins = tuple((config or {}).get("hypothetical_quantity_margins", DEFAULT_MARGINS))
        out = []
        for c in self._quantity_comparisons(inputs):
            if c["result"]["status"] != "COMPARABLE":
                continue
            for row in _core().quantity_scenarios(str(c["assigned"]), c["reference"].quantity, margins):
                out.append(Scenario(
                    scenario_id=f"S-{inputs.transaction.transaction_id}-{c['project_id']}-{row['margin']}",
                    label=f"Lot {c['project_id']} : marge hypothétique {row['margin']} (hypothèse fictive, pas une tolérance)",
                    assumption_ids=(f"MARGIN_{row['margin']}",),
                    inputs={"assigned": str(c["assigned"]), "baseline": c["reference"].quantity, "margin": row["margin"]},
                    outputs={"hypothetical_bound": row["hypothetical_bound"], "residual": row["residual"]},
                    evidence_refs=(EvidenceRef(source_record_id=c["reference"].reference_id),)))
        return out

    # ---------------------------------------------------------- hypotheses
    def test_hypotheses(self, inputs: TransactionInputs, findings: list[Finding],
                        pending_second_package: bool = False) -> list[Hypothesis]:
        """Code-tested playbook hypotheses; a free-text claim alone never supports one."""
        qty = next((f for f in findings if f.family is FindingFamily.QUANTITY), None)
        comps = self._quantity_comparisons(inputs)
        projects = {c["project_id"] for c in comps if c["result"]["status"] == "COMPARABLE"}
        base = dict(case_version=inputs.case_version, scope=inputs.transaction.transaction_id)
        if qty is None or qty.status is FindingStatus.INSUFFICIENT:
            status_second = HypothesisStatus.NOT_APPLICABLE
        elif qty.status is FindingStatus.EXPLAINED and len(projects) >= 2:
            status_second = HypothesisStatus.SUPPORTED
        else:
            status_second = HypothesisStatus.UNRESOLVED
        support = tuple(EvidenceRef(source_record_id=a.allocation_id) for c in comps for a in c["allocations"])
        return [
            Hypothesis(hypothesis_id="H-SECOND-PACKAGE", statement_template_id="SECOND_AUTHORIZED_PACKAGE",
                       test_id="ACCEPTED_ALLOCATIONS_WITHIN_REFERENCES", status=status_second,
                       supporting_refs=support if status_second is HypothesisStatus.SUPPORTED else (),
                       missing_evidence_types=() if status_second is HypothesisStatus.SUPPORTED else
                       (("ALLOCATION_RESPONSE_UNDER_REVIEW",) if pending_second_package else ("ALLOCATION_RESPONSE",)),
                       **base),
            Hypothesis(hypothesis_id="H-STOCK", statement_template_id="AUTHORIZED_STOCK", test_id="NO_STOCK_RECORD_SUPPLIED",
                       status=HypothesisStatus.UNRESOLVED if qty and qty.status is FindingStatus.UNRESOLVED else HypothesisStatus.NOT_APPLICABLE,
                       missing_evidence_types=("STOCK_RECORD",), **base),
            Hypothesis(hypothesis_id="H-AMENDMENT", statement_template_id="PROCUREMENT_AMENDMENT", test_id="NO_AMENDMENT_SUPPLIED",
                       status=HypothesisStatus.UNRESOLVED if qty and qty.status is FindingStatus.UNRESOLVED else HypothesisStatus.NOT_APPLICABLE,
                       missing_evidence_types=("AMENDED_ALLOCATION_REFERENCE",), **base),
        ]

    # --------------------------------------------------------------- score
    def score_transaction(self, findings: list[Finding], applicability: set[FindingFamily]) -> ScoreResult:
        core = _core()
        fs = [core.Finding(transaction_id=f.transaction_id, family=f.family.value, status=f.status.value,
                           severity=f.severity if f.status in (FindingStatus.UNRESOLVED, FindingStatus.EXPLAINED) else None,
                           evidence_ids=tuple(r.source_record_id or r.document_id or "" for r in f.evidence_refs))
              for f in findings if f.family in applicability]
        r = core.score_transaction(fs, {f.value for f in applicability})
        return ScoreResult(transaction_id=findings[0].transaction_id if findings else "", review_index=r["review_index"],
                           evidence_coverage=r["evidence_coverage"], coverage_complete=r["coverage_complete"],
                           evaluable_families=tuple(FindingFamily(x) for x in r["evaluable_families"]),
                           unknown_families=tuple(FindingFamily(x) for x in r["unknown_families"]),
                           contributions=r["contributions"], method=f"{r['method']}/{INTERIM_CALC_VERSION}")

    def aggregate_company(self, transaction_scores: list[ScoreResult]) -> int | None:
        return _core().enterprise_index([s.model_dump() for s in transaction_scores])


def get_checks_engine():
    """Lane B's engine when merged (module ``boussla.checks`` exposing the
    ChecksEngine functions), else this interim adapter."""
    spec = importlib.util.find_spec("boussla.checks")
    if spec is not None:
        from boussla import checks  # type: ignore[attr-defined]
        from boussla.contracts import ChecksEngine
        if isinstance(checks, ChecksEngine):
            return checks
    return InterimChecks()
