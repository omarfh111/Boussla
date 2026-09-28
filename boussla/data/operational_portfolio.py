"""Deterministic synthetic operational facts; no service, network or scoring writes.

Management functions are pure copy-on-write data operations, not authorization APIs.
Lane A must authorize callers and persist the returned facts explicitly.
"""
from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path

from boussla.contracts import Enterprise, Project, TransactionInputs
from boussla.data.screening_population import _input, _instant

VERSION = "SYNTHETIC_OPERATIONAL_V1"
AS_OF = "2026-01-10T00:00:00+00:00"
PERIODS = tuple(f"2025-{month:02d}" for month in range(1, 13))
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/operational_portfolio/portfolio.json"
NAMES = (
    ("Atelier Horizon", "Fabrication"), ("Négoce Jasmin", "Commerce de matériaux"),
    ("Équipements Azur", "Équipement professionnel"), ("Mobilité Olive", "Transport"),
    ("Fournitures Dune", "Distribution"), ("Atelier Cèdre", "Fabrication"),
    ("Services Corail", "Services"), ("Logistique Safran", "Logistique"),
    ("Bâtiments Aube", "Construction"), ("Réserve Atlas", "Commerce de gros"),
    ("Machines Iris", "Équipement industriel"), ("Travaux Opale", "Construction"),
)


def _event(number: int, sequence: int, month: int, position: int) -> dict:
    cid = f"SYN-OP-{number:03d}"
    conflict = number in {2, 12} and month >= 10
    source = _input(cid, month, 10000 + number * 100,
                    counterpart=number != 4, conflict=conflict,
                    payment_fraction=2 if number in {8, 12} and month >= 10 else 1)
    old = source["transaction"]["transaction_id"]
    tid = f"{cid}-TX-{sequence:03d}"
    source = json.loads(json.dumps(source).replace(old, tid))
    day = date(2025, month, 5 + position * 5)
    # Shift the underlying event and all linked timestamps together.
    old_day = date(2025, month, 10)
    def shift(value):
        if isinstance(value, dict):
            return {k: shift(v) for k, v in value.items()}
        if isinstance(value, list):
            return [shift(v) for v in value]
        if isinstance(value, str) and value.startswith(f"2025-{month:02d}-"):
            return (date.fromisoformat(value[:10]) + (day-old_day)).isoformat() + value[10:]
        return value
    source = shift(source)
    source["as_of"] = AS_OF
    source["case_id"] = f"{cid}-CASE"
    seller = f"{cid}-SUPPLIER-{1 if number == 12 and month >= 10 else (sequence-1) % 3+1}"
    source = json.loads(json.dumps(source).replace("SYNTHETIC-SELLER", seller))
    project_id = f"{cid}-P-{sequence:03d}"
    source = json.loads(json.dumps(source).replace(f"{cid}-P1", project_id))
    for doc in source["documents"]:
        doc.update(case_id=source["case_id"], confidentiality_scope="SYNTHETIC_OPERATIONAL",
                   uploader_actor_id=f"{cid}-COMPANY" if doc["acquisition_channel"] == "COMPANY_UPLOAD" else f"{seller}-RECORDS")
    for invoice in source["invoice_observations"]:
        invoice["invoice_version"] = "1"
        invoice["buyer_mf_raw"] = f"SYNTHETIC-MF-OP-{number:03d}"
        invoice["lines"][0]["item_description"] = "Unités de matériau synthétiques"
    if number in {3, 12} and month == 12:
        # Equal total, different stated quantity/price: a line conflict, not a new sale.
        line = source["invoice_observations"][1]["lines"][0]
        line["quantity"] = "80"
        line["unit_price_millimes"] = line["line_net_millimes"] // 80
    if number == 5 and month in {7, 8}:
        available = _instant(day + timedelta(days=65))
        for invoice in source["invoice_observations"]:
            invoice["available_at"] = available
        for doc in source["documents"]:
            doc["received_at"] = available
    projects = []
    no_project = number in {4, 7, 8, 11}
    purpose = "LONG_LIVED_ASSET" if no_project else "CONSTRUCTION_PROJECT"
    if no_project:
        source["transaction"]["project_id"] = None
        source["allocations"], source["quantity_references"] = [], []
        for invoice in source["invoice_observations"]:
            invoice["lines"][0].update(project_id=None, item_description="Véhicules professionnels synthétiques",
                                       normalized_item_code="SYN-VEHICLE", quantity="2",
                                       unit_price_millimes=invoice["lines"][0]["line_net_millimes"] // 2)
        for delivery in source["deliveries"]:
            delivery.update(item_code="SYN-VEHICLE", quantity="2")
    else:
        projects.append({"project_id": project_id, "company_id": cid, "label": f"Lot synthétique {month:02d}",
                         "project_type": "CONSTRUCTION", "planned_start": day.isoformat(),
                         "planned_end": f"2026-{month:02d}-{day.day:02d}", "status": "IN_PROGRESS"})
        for ref in source["quantity_references"]:
            ref["valid_to"] = date(2025, month, monthrange(2025, month)[1]).isoformat()
        if number in {9, 12} and month == 12:
            second = f"{project_id}-B"
            projects.append({**projects[0], "project_id": second, "label": "Second lot synthétique"})
            source["allocations"][0]["quantity"] = "70"
            source["allocations"].append({**source["allocations"][0], "allocation_id": f"{tid}-ALLOC-B",
                                           "target_project_id": second, "quantity": "30"})
            source["quantity_references"][0]["quantity"] = "50"
            source["quantity_references"].append({**source["quantity_references"][0], "reference_id": f"{tid}-REF-B",
                                                   "project_id": second, "quantity": "50"})
        if number == 10:
            source["allocations"][0].update(target_project_id=None, target_type="WAREHOUSE")
            purpose = "RESALE"
    if number == 11 and month == 11:
        gross = source["invoice_observations"][0]["gross_millimes"]
        source["settlement_adjustments"] = [{"adjustment_id": f"{tid}-CREDIT", "transaction_id": tid,
            "kind": "CREDIT_NOTE", "signed_millimes": -gross // 5, "supporting_refs": [f"{tid}-CREDIT-SOURCE"],
            "accepted_by": "SYNTHETIC_REVIEWER", "status": "ACCEPTED"}]
        payable = gross + source["settlement_adjustments"][0]["signed_millimes"]
        source["payments"][0]["amount_millimes"] = payable
        source["payment_allocations"][0]["allocated_millimes"] = payable
    if number == 11 and month == 12:
        source["payments"][0]["status"] = "REVERSED"
    source["context_claims"] = [{"claim_id": f"{tid}-CLAIM", "company_id": cid, "transaction_id": tid,
        "project_id": None if no_project else project_id, "purpose_category": purpose,
        "purpose_text": "Achat déclaré de véhicules professionnels" if no_project else
            "Stock déclaré pour affectation ultérieure" if number == 10 else "Travaux déclarés sur un lot synthétique",
        "beneficiary_type": "COMPANY", "planned_start": day.isoformat(),
        "planned_end": f"2026-{month:02d}-{day.day:02d}", "stage": "IN_PROGRESS",
        "reported_stock_qty": "100" if number == 10 else None,
        "author_actor_id": f"{cid}-COMPANY", "submitted_at": _instant(day+timedelta(days=2)),
        "declared_horizon": "LONGER_HORIZON"}]
    for doc in source["documents"]:
        invoice = next(i for i in source["invoice_observations"] if i["document_id"] == doc["document_id"])
        doc["sha256"] = sha256(json.dumps(invoice, sort_keys=True).encode()).hexdigest()
    # Preserve the frozen V1 fixture schema; later runtime fields are not synthetic facts.
    serialized = TransactionInputs.model_validate(source).model_dump(
        mode="json", exclude={"payments": {"__all__": {"payment_method"}}})
    return {"inputs": serialized,
            "projects": [Project.model_validate(p).model_dump(mode="json") for p in projects]}


def _snapshot(events: list[dict]) -> dict:
    payable = settled = outflows = 0
    refs = []
    outstanding = 0
    for event in events:
        i = event["inputs"]
        invoice = next(v for v in i["invoice_observations"] if v["perspective"] == "BUYER_RECEIVED")
        net_payable = invoice["gross_millimes"] + sum(a["signed_millimes"] for a in i["settlement_adjustments"])
        payments = {p["payment_id"]: p for p in i["payments"] if p["status"] == "SETTLED"}
        paid = sum(a["allocated_millimes"] for a in i["payment_allocations"] if a["payment_id"] in payments)
        payable += net_payable
        settled += paid
        outflows += sum(p["amount_millimes"] for p in payments.values())
        outstanding += max(0, net_payable-paid)
        refs.extend([invoice["document_id"], *(p["source_record_id"] for p in i["payments"])])
    return {"data_kind": "SYNTHETIC", "as_of": AS_OF, "currency": "TND", "observed_inflows_millimes": 0,
            "observed_outflows_millimes": outflows, "observed_settlements_millimes": settled,
            "documented_payable_millimes": payable, "outstanding_documented_payable_millimes": outstanding,
            "source_ids": sorted(refs), "scope": "GENERATED_PURCHASE_LEDGER_ONLY",
            "statement": "Contexte synthétique autorisé pour la démo uniquement ; aucune connexion bancaire, aucune preuve. Échéances non établies."}


def generate_operational_portfolio() -> dict:
    """Twelve curated enterprises; fixed event schedule, no clock or randomness."""
    enterprises = []
    for number, (name, sector) in enumerate(NAMES, 1):
        cid = f"SYN-OP-{number:03d}"
        counts = [1] * 12
        if number == 5:
            counts = [1]*8 + [0, 0, 2, 2]
        if number == 6:
            counts[-1] = 4
        if number == 7:
            counts[-2:] = [2, 0]
        events = []
        for month, count in enumerate(counts, 1):
            for position in range(count):
                events.append(_event(number, len(events)+1, month, position))
        identity = Enterprise(company_id=cid, synthetic_mf=f"SYNTHETIC-MF-OP-{number:03d}",
                              display_name=f"SYNTHÉTIQUE — {name}", sector=sector, created_on=date(2024, 1, 1))
        sources = {}
        for event in events:
            inputs = event["inputs"]
            source_ids = [p["source_record_id"] for p in inputs["payments"]]
            for kind in ("allocations", "quantity_references", "deliveries", "settlement_adjustments"):
                for row in inputs[kind]:
                    source_ids.extend(row.get("source_refs", row.get("supporting_refs", [])))
            for ref in source_ids:
                sources[ref] = {"source_id": ref, "company_id": cid,
                    "transaction_id": inputs["transaction"]["transaction_id"], "data_kind": "SYNTHETIC",
                    "description": "Enregistrement structuré synthétique ; provenance simulée, aucune pièce officielle."}
        enterprises.append({"identity": identity.model_dump(mode="json"), "case_id": f"{cid}-CASE",
            "history_start": PERIODS[0], "history_end": PERIODS[-1],
            "coverage": [{"period": p, "status": "COMPLETE_SYNTHETIC_LEDGER", "source_id": f"{cid}-COVERAGE-{p}"} for p in PERIODS],
            "events": events, "source_records": list(sources.values()),
            "synthetic_authorized_financial_snapshot": _snapshot(events)})
    return {"version": VERSION, "data_kind": "SYNTHETIC", "as_of": AS_OF, "enterprises": enterprises}


def _validate_enterprise(row: dict) -> None:
    if set(row) != {"identity", "case_id", "history_start", "history_end", "coverage", "events",
                    "source_records", "synthetic_authorized_financial_snapshot"}:
        raise ValueError("unexpected enterprise fields")
    identity = Enterprise.model_validate(row["identity"])
    cid = identity.company_id
    if not cid.startswith("SYN-") or not identity.synthetic_mf.startswith("SYNTHETIC-"):
        raise ValueError("synthetic identities required")
    covered = set()
    for coverage in row["coverage"]:
        if (set(coverage) != {"period", "status", "source_id"}
                or coverage["status"] != "COMPLETE_SYNTHETIC_LEDGER"
                or not coverage["source_id"].startswith(cid+"-") or coverage["period"] in covered):
            raise ValueError("invalid synthetic coverage")
        date.fromisoformat(coverage["period"]+"-01")
        covered.add(coverage["period"])
    seen = set()
    for event in row["events"]:
        if set(event) != {"inputs", "projects"}:
            raise ValueError("unexpected event fields")
        i = TransactionInputs.model_validate(event["inputs"])
        tid = i.transaction.transaction_id
        if (i.company_id != cid or i.transaction.buyer_company_id != cid or i.case_id != row["case_id"]
                or tid in seen or not tid.startswith(cid+"-")):
            raise ValueError("duplicate transaction or cross-company scope")
        seen.add(tid)
        if any(d.subject_company_id != cid or d.case_id != i.case_id for d in i.documents):
            raise ValueError("cross-company document")
        if any(o.transaction_id != tid or o.buyer_company_id != cid for o in i.invoice_observations):
            raise ValueError("cross-company invoice")
        if set(i.transaction.invoice_observation_ids) != {o.observation_id for o in i.invoice_observations}:
            raise ValueError("invoice linkage mismatch")
        if any(p.payer_company_id != cid or p.payee_company_id != i.transaction.seller_company_id for p in i.payments):
            raise ValueError("cross-company payment")
        if any(a.transaction_id != tid for a in (*i.allocations, *i.payment_allocations, *i.deliveries, *i.settlement_adjustments)):
            raise ValueError("cross-transaction fact")
        if any(m.company_id not in {cid, i.transaction.seller_company_id} for m in i.identity_mappings):
            raise ValueError("cross-company mapping")
        if any(c.company_id != cid for c in i.context_claims) or any(r.company_id != cid for r in i.quantity_references):
            raise ValueError("cross-company context/reference")
        if any(Project.model_validate(p).company_id != cid for p in event["projects"]):
            raise ValueError("cross-company project")
    if any(source["company_id"] != cid for source in row["source_records"]):
        raise ValueError("cross-company source record")
    if any(set(source) != {"source_id", "company_id", "transaction_id", "data_kind", "description"}
           or source["data_kind"] != "SYNTHETIC" or not source["source_id"].startswith(cid+"-")
           for source in row["source_records"]):
        raise ValueError("invalid structured synthetic source")
    if any(source["transaction_id"] not in seen for source in row["source_records"]):
        raise ValueError("unlinked source record")
    if row["synthetic_authorized_financial_snapshot"] != _snapshot(row["events"]):
        raise ValueError("financial snapshot must match synthetic ledger")


def seed_portfolio(path: Path | None = None) -> dict:
    """Load only operational facts, or regenerate when path is omitted. No DB writes."""
    result = generate_operational_portfolio() if path is None else json.loads(Path(path).read_text(encoding="utf-8"))
    if (set(result) != {"version", "data_kind", "as_of", "enterprises"}
            or result.get("version") != VERSION or result.get("data_kind") != "SYNTHETIC"):
        raise ValueError("unsupported operational portfolio")
    ids = []
    for row in result["enterprises"]:
        _validate_enterprise(row)
        ids.append(row["identity"]["company_id"])
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate enterprise")
    return result


def list_enterprises(portfolio: dict) -> list[Enterprise]:
    return [Enterprise.model_validate(row["identity"]) for row in portfolio["enterprises"]]


def enterprise_facts(portfolio: dict, company_id: str) -> dict:
    """Explicit scope; never fall back to another enterprise on unknown ID."""
    for row in portfolio["enterprises"]:
        if row["identity"]["company_id"] == company_id:
            _validate_enterprise(row)
            return deepcopy(row)
    raise KeyError(company_id)


def transaction_inputs(portfolio: dict, company_id: str) -> tuple[TransactionInputs, ...]:
    return tuple(TransactionInputs.model_validate(e["inputs"]) for e in enterprise_facts(portfolio, company_id)["events"])


def reset_portfolio(portfolio: dict) -> dict:
    """Return a fresh default portfolio; caller retains the original unmodified."""
    return generate_operational_portfolio()


def add_synthetic_enterprise(portfolio: dict, enterprise: dict | Enterprise) -> dict:
    """Add a validated bundle, or create an empty synthetic enterprise from identity."""
    if isinstance(enterprise, Enterprise):
        enterprise = {"identity": enterprise.model_dump(mode="json"), "case_id": f"{enterprise.company_id}-CASE",
            "history_start": PERIODS[0], "history_end": PERIODS[-1], "coverage": [], "events": [],
            "source_records": [], "synthetic_authorized_financial_snapshot": _snapshot([])}
    _validate_enterprise(enterprise)
    if enterprise["identity"]["company_id"] in {e.company_id for e in list_enterprises(portfolio)}:
        raise ValueError("enterprise already exists")
    result = deepcopy(portfolio)
    result["enterprises"].append(deepcopy(enterprise))
    return result


def case_facts(portfolio: dict, company_id: str) -> dict[str, list]:
    """A-ready typed fact batches for one enterprise; does not open/write a store."""
    row = enterprise_facts(portfolio, company_id)
    mapping = {"invoice_observations": "invoice_observation", "payments": "payment",
        "payment_allocations": "payment_allocation", "settlement_adjustments": "settlement_adjustment",
        "identity_mappings": "identity_mapping", "allocations": "allocation", "quantity_references": "quantity_reference",
        "context_claims": "context_claim", "deliveries": "delivery", "documents": "document"}
    facts = {kind: [] for kind in (*mapping.values(), "transaction", "project")}
    for event in row["events"]:
        i = TransactionInputs.model_validate(event["inputs"])
        facts["transaction"].append(i.transaction)
        facts["project"].extend(Project.model_validate(p) for p in event["projects"])
        for attribute, kind in mapping.items():
            facts[kind].extend(getattr(i, attribute))
    return facts


def delete_synthetic_enterprise(portfolio: dict, company_id: str) -> dict:
    enterprise_facts(portfolio, company_id)  # validate existence and scope first
    result = deepcopy(portfolio)
    result["enterprises"] = [r for r in result["enterprises"] if r["identity"]["company_id"] != company_id]
    return result


if __name__ == "__main__":
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(seed_portfolio(), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Wrote deterministic synthetic operational portfolio")
