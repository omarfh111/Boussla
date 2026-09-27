"""Runtime wiring of lane B's synthetic operational portfolio — lane A.

Lane B owns the data and its pure management functions
(``boussla.data.operational_portfolio``) and the neutral history rules
(``boussla.history_signals``). This module only persists the current portfolio
state next to the case database, materializes each enterprise as a normal versioned
case, and exposes typed history signals / financial snapshots for officer views.
Authorization (DEMO_OPERATOR) is enforced by the service, never here.
"""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path

from boussla.contracts import (
    CompanyHistorySignal, Enterprise, FinancialSnapshotView, HistorySignalCode, Mode,
)
from boussla.data import operational_portfolio as op
from boussla.history_signals import analyze_self_history
from boussla.seed import fact_id
from boussla.store import CaseStore, stable_hash

SYNTHETIC_ID = re.compile(r"SYN-[A-Z0-9-]{1,40}")
SEED_ACTOR = "DEMO-OPERATOR"


def _fact_id(kind: str, model) -> str:
    if kind == "settlement_adjustment":
        return model.adjustment_id
    return fact_id(kind, model)


class PortfolioRuntime:
    """Current synthetic portfolio (JSON state validated by lane B on every load/save)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._data: dict | None = None
        self._signals: dict[str, tuple[CompanyHistorySignal, ...]] = {}

    # ----------------------------------------------------------------- state
    @property
    def data(self) -> dict:
        with self._lock:
            if self._data is None:
                if self.path.is_file():
                    self._data = op.seed_portfolio(self.path)  # lane B validation
                else:
                    self._save(op.seed_portfolio(op.FIXTURE if op.FIXTURE.is_file() else None))
            return self._data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".part")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        self._data = data
        self._signals.clear()

    def enterprises(self) -> list[Enterprise]:
        return op.list_enterprises(self.data)

    def is_member(self, company_id: str) -> bool:
        return any(e.company_id == company_id for e in self.enterprises())

    def bundle(self, company_id: str) -> dict | None:
        try:
            return op.enterprise_facts(self.data, company_id)
        except KeyError:
            return None

    @staticmethod
    def case_id(company_id: str) -> str:
        return f"{company_id}-CASE"

    @property
    def as_of(self) -> datetime:
        return datetime.fromisoformat(self.data["as_of"])

    # ------------------------------------------------------- management (lane B)
    def reset(self) -> None:
        with self._lock:
            self._save(op.reset_portfolio(self.data))

    def add(self, enterprise: Enterprise) -> None:
        with self._lock:
            self._save(op.add_synthetic_enterprise(self.data, enterprise))

    def delete(self, company_id: str) -> None:
        with self._lock:
            self._save(op.delete_synthetic_enterprise(self.data, company_id))

    # ------------------------------------------------------------ persistence
    def materialize(self, store: CaseStore, company_id: str) -> str:
        """Create the enterprise's case at version 1 from ``case_facts`` if absent."""
        case_id = self.case_id(company_id)
        if store.case_exists(case_id):
            return case_id
        facts = op.case_facts(self.data, company_id)
        with store.write(case_id) as tx:
            tx.create_case(company_id, "seed")
            for kind, rows in facts.items():
                for row in rows:
                    tx.put(kind, _fact_id(kind, row), row)
            tx.commit_version("Portefeuille synthétique opérationnel chargé (DEMO_OPERATOR)")
            tx.event("SEED", SEED_ACTOR, "Historique synthétique de 12 mois chargé ; provenance simulée")
        return case_id

    def materialize_all(self, store: CaseStore) -> list[str]:
        return [self.materialize(store, e.company_id) for e in self.enterprises()]

    # --------------------------------------------------------------- read models
    def signals(self, company_id: str, as_of=None) -> list[CompanyHistorySignal]:
        """CompanyHistorySignalProvider: lane B ``analyze_history`` at the portfolio cutoff."""
        with self._lock:
            if company_id not in self._signals:
                bundle = self.bundle(company_id)
                if bundle is None:
                    self._signals[company_id] = ()
                else:
                    raw = analyze_self_history(op.transaction_inputs(self.data, company_id), company_id=company_id,
                                          as_of=self.as_of,
                                          coverage={r["period"]: r["source_id"] for r in bundle["coverage"]})
                    self._signals[company_id] = tuple(CompanyHistorySignal(
                        signal_id=f"SIG-{stable_hash([s.reason_code, s.period, s.metric])[:10].upper()}",
                        company_id=company_id, reason_code=HistorySignalCode(s.reason_code), period=s.period,
                        metric=s.metric, observed_value=s.observed_value, baseline_value=s.baseline_value,
                        baseline_periods=s.baseline_periods, evidence_source_ids=s.evidence_source_ids,
                        explanation_fr=s.explanation, method=s.method, mode=Mode.LIVE) for s in raw)
            return list(self._signals[company_id])

    def financial_snapshot(self, company_id: str) -> FinancialSnapshotView | None:
        bundle = self.bundle(company_id)
        if bundle is None:
            return None
        s = bundle["synthetic_authorized_financial_snapshot"]
        return FinancialSnapshotView(
            as_of=s["as_of"], currency=s["currency"], observed_outflows_millimes=s["observed_outflows_millimes"],
            observed_settlements_millimes=s["observed_settlements_millimes"],
            documented_payable_millimes=s["documented_payable_millimes"],
            outstanding_documented_payable_millimes=s["outstanding_documented_payable_millimes"],
            scope=s["scope"], statement_fr=s["statement"], source_count=len(s["source_ids"]))
