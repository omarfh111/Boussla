"""Lane B implementation of the shared pure ChecksEngine protocol."""

from __future__ import annotations

from boussla import scoring
from boussla.checks.invoices import compare_invoice_observations
from boussla.checks.quantities import compare_quantity_allocations
from boussla.checks.settlements import reconcile_settlements
from boussla.contracts import Finding, FindingFamily, Scenario, ScoreResult, TransactionInputs
from boussla.scenarios import run_scenarios


class ChecksEngineV4:
    """Deterministic checks with no persistence, provider calls or clock reads."""

    def evaluate_transaction(self, inputs: TransactionInputs) -> list[Finding]:
        return [
            compare_invoice_observations(inputs),
            reconcile_settlements(inputs),
            compare_quantity_allocations(inputs),
        ]

    def run_scenarios(self, inputs: TransactionInputs, config: dict) -> list[Scenario]:
        return run_scenarios(inputs, config)

    def score_transaction(self, findings: list[Finding],
                          applicability: set[FindingFamily]) -> ScoreResult:
        return scoring.score_transaction(findings, applicability)

    def aggregate_company(self, transaction_scores: list[ScoreResult]) -> int | None:
        return scoring.aggregate_company(transaction_scores)
