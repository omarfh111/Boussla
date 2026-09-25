"""Synthetic demo seeding — lane A (DEMO_OPERATOR only).

Loads ``docs/build_lock/fixtures/observed`` into the case store as version 1.
Never reads ``fixtures/evaluation_only``: evaluation truth must not reach the
runtime (TESTS_AND_8H_PLAN.md test 29). Fixture-only fields (``synthetic``,
``note``, ``relative_path``...) are dropped; source lineage comes from the
fixture's server-side metadata, never from PDF labels.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from boussla.config import FIXTURE_ROOT
from boussla.contracts import (
    Allocation, ContextClaim, Delivery, Document, Enterprise, IdentityMapping, InvoiceObservation, Payment,
    PaymentAllocation, Project, QuantityReference, Transaction,
)
from boussla.store import CaseStore

OBSERVED = FIXTURE_ROOT / "observed"

# store kind -> (fixture file, model, id field)
KINDS: dict[str, tuple[str, type, str]] = {
    "invoice_observation": ("invoice_observations.json", InvoiceObservation, "observation_id"),
    "transaction": ("transactions.json", Transaction, "transaction_id"),
    "payment": ("payments.json", Payment, "payment_id"),
    "identity_mapping": ("identity_mappings.json", IdentityMapping, "mapping_id"),
    "allocation": ("allocations.json", Allocation, "allocation_id"),
    "quantity_reference": ("quantity_references.json", QuantityReference, "reference_id"),
    "context_claim": ("context_claims.json", ContextClaim, "claim_id"),
    "delivery": ("deliveries.json", Delivery, "delivery_id"),
}


def _json(name: str):
    return json.loads((OBSERVED / name).read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict]:
    with (OBSERVED / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _only_fields(model: type, row: dict) -> dict:
    return {k: v for k, v in row.items() if k in model.model_fields}


def load_enterprises() -> dict[str, Enterprise]:
    return {r["company_id"]: Enterprise(**_only_fields(Enterprise, r)) for r in _csv("entreprises.csv")}


def load_projects() -> list[Project]:
    return [Project(project_id=r["project_id"], company_id=r["company_id"], label=r["label"],
                    project_type=r["project_type"], planned_start=r["planned_start"] or None,
                    planned_end=r["planned_end"] or None, reference_ids=(r["reference_id"],), status=r["status"])
            for r in _csv("projects.csv")]


def load_case_seed() -> dict:
    return _json("case_seed.json")


def load_fixture_facts() -> dict[str, list]:
    """All observed facts as validated contract models, keyed by store kind."""
    seed = load_case_seed()
    facts: dict[str, list] = {kind: [model(**_only_fields(model, r)) for r in _json(file)]
                              for kind, (file, model, _) in KINDS.items()}
    facts["payment_allocation"] = [PaymentAllocation(**r) for r in _json("payment_allocations.json")]
    facts["project"] = [p for p in load_projects() if p.company_id == seed["company_id"]]
    docs = []
    for row in _json("documents.json"):
        if row["document_id"] in seed["initial_document_ids"]:
            d = Document(**_only_fields(Document, row))
            docs.append(d.model_copy(update={"local_path": str(FIXTURE_ROOT.parent / row["relative_path"])}))
    facts["document"] = docs
    return facts


def fact_id(kind: str, model) -> str:
    if kind == "payment_allocation":
        return f"{model.payment_id}:{model.transaction_id}"
    if kind == "project":
        return model.project_id
    if kind == "document":
        return model.document_id
    return getattr(model, KINDS[kind][2])


def seed_demo_case(store: CaseStore, actor_id: str = "DEMO-OPERATOR") -> str:
    """Create CASE-BRICKS-001 at version 1 if absent. Returns the case id."""
    seed = load_case_seed()
    case_id = seed["case_id"]
    if store.case_exists(case_id):
        return case_id
    facts = load_fixture_facts()
    with store.write(case_id) as tx:
        tx.create_case(seed["company_id"], "seed")
        for kind, rows in facts.items():
            for row in rows:
                tx.put(kind, fact_id(kind, row), row)
        tx.commit_version("Initialisation depuis les fixtures synthétiques (DEMO_OPERATOR)")
        tx.event("SEED", actor_id, "Dossier synthétique chargé ; provenance simulée pour la contrepartie")
    return case_id


def fixture_path(relative: str) -> Path:
    return FIXTURE_ROOT.parent / relative
