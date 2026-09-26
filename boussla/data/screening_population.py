"""Synthetic structured company histories for exercising the existing V4 checks.

Every source view starts from one fictional purchase event. The eight generation
patterns vary source availability or observations; they are not outcome labels.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from random import Random

from boussla.contracts import TransactionInputs

DEFAULT_SEED = 20260926
POPULATION_VERSION = "SYNTHETIC_SCREENING_V1"
PATTERN_COUNT = 8


def _instant(day: date) -> str:
    return datetime.combine(day, datetime.min.time(), timezone.utc).isoformat()


def _document(document_id: str, company_id: str, case_id: str, day: date,
              channel: str, origin: str, payload: str) -> dict:
    return {
        "document_id": document_id, "subject_company_id": company_id,
        "case_id": case_id, "original_filename": f"{document_id}.synthetic.json",
        "local_path": "NOT_MATERIALIZED", "sha256": sha256(payload.encode()).hexdigest(),
        "media_type": "application/json", "received_at": _instant(day),
        "uploader_actor_id": "SYNTHETIC_GENERATOR", "acquisition_channel": channel,
        "origin_group_id": origin, "confidentiality_scope": "SYNTHETIC_EVALUATION",
        "extraction_status": "FIXTURE_FIELDS_KNOWN",
    }


def _input(company_id: str, month: int, unit_price: int, *,
           counterpart: bool = True, conflict: bool = False,
           confirmed: bool = True, payment_fraction: int = 1,
           quantity_limit: int = 100, reallocated: bool = False,
           case_version: int = 1) -> dict:
    day = date(2025, month, 10)
    tx_id = f"{company_id}-TX-{month:02d}"
    case_id = f"CASE-{tx_id}"
    seller_id = "SYNTHETIC-SELLER"
    net = 100 * unit_price
    tax = net * 19 // 100
    gross = net + tax
    buyer_doc = f"{tx_id}-BUY"
    seller_doc = f"{tx_id}-SELL"
    line = {
        "line_id": f"{tx_id}-LINE", "item_description": "Fictional masonry units",
        "normalized_item_code": "SYN-MASONRY-UNIT", "quantity": "100",
        "unit": "piece", "unit_price_millimes": unit_price,
        "line_net_millimes": net, "project_id": f"{company_id}-P1",
    }
    invoice = {
        "observation_id": f"{tx_id}-BUYER-VIEW", "document_id": buyer_doc,
        "transaction_id": tx_id, "perspective": "BUYER_RECEIVED",
        "issuer_company_id": seller_id, "issuer_mf_raw": "SYNTHETIC-SELLER-MF",
        "buyer_company_id": company_id, "buyer_mf_raw": f"SYNTHETIC-MF-{company_id}",
        "invoice_number": f"SYN-{tx_id}", "issued_on": day.isoformat(),
        "available_at": _instant(day + timedelta(days=2)), "currency": "TND",
        "net_millimes": net, "tax_millimes": tax, "gross_millimes": gross,
        "lines": [line], "transcription_status": "CONFIRMED" if confirmed else "PROPOSED",
        "origin_group_id": f"{tx_id}-BUYER-ORIGIN",
    }
    seller = {
        **invoice, "observation_id": f"{tx_id}-SELLER-VIEW",
        "document_id": seller_doc, "perspective": "SELLER_ISSUED",
        "origin_group_id": f"{tx_id}-SELLER-ORIGIN",
        "net_millimes": net + net // 4 if conflict else net,
        "tax_millimes": tax + tax // 4 if conflict else tax,
        "gross_millimes": gross + gross // 4 if conflict else gross,
        "lines": [{**line,
                   "unit_price_millimes": unit_price + unit_price // 4 if conflict else unit_price,
                   "line_net_millimes": net + net // 4 if conflict else net}],
    }
    observations = [invoice, seller] if counterpart else [invoice]
    documents = [_document(buyer_doc, company_id, case_id, day + timedelta(days=2),
                           "COMPANY_UPLOAD", invoice["origin_group_id"], str(invoice))]
    if counterpart:
        documents.append(_document(seller_doc, company_id, case_id, day + timedelta(days=2),
                                   "SIMULATED_COUNTERPARTY_REFERENCE", seller["origin_group_id"],
                                   str(seller)))

    payments = []
    payment_allocations = []
    mappings = []
    allocations = []
    references = []
    deliveries = []
    if confirmed:
        payment_id = f"{tx_id}-PAY"
        payment_source = f"{tx_id}-SETTLEMENT-SOURCE"
        payment_amount = gross // 2 if payment_fraction == 2 else gross
        payments = [{
            "payment_id": payment_id, "source_record_id": payment_source,
            "payer_company_id": company_id, "payee_company_id": seller_id,
            "payer_mapping_ref": f"{tx_id}-PAYER-MAP",
            "payee_mapping_ref": f"{tx_id}-PAYEE-MAP", "currency": "TND",
            "amount_millimes": payment_amount, "status": "SETTLED",
            "occurred_at": _instant(day + timedelta(days=5)),
            "available_at": _instant(day + timedelta(days=6)),
            "origin_group_id": f"{tx_id}-PAYMENT-ORIGIN",
        }]
        payment_allocations = [{
            "payment_id": payment_id, "transaction_id": tx_id,
            "allocated_millimes": payment_amount, "accepted_by": "SYNTHETIC_REVIEWER",
            "accepted_at": _instant(day + timedelta(days=7)),
        }]
        mappings = [
            {"mapping_id": f"{tx_id}-PAYER-MAP", "company_id": company_id,
             "source_record_id": payment_source, "status": "ACCEPTED_SYNTHETIC_FIXTURE",
             "verified_by": "SYNTHETIC_REVIEWER"},
            {"mapping_id": f"{tx_id}-PAYEE-MAP", "company_id": seller_id,
             "source_record_id": payment_source, "status": "ACCEPTED_SYNTHETIC_FIXTURE",
             "verified_by": "SYNTHETIC_REVIEWER"},
        ]
        quantities = [(f"{company_id}-P1", 50 if reallocated else 100)]
        if reallocated:
            quantities.append((f"{company_id}-P2", 50))
        for project_id, quantity in quantities:
            allocations.append({
                "allocation_id": f"{tx_id}-ALLOC-{project_id}",
                "transaction_id": tx_id, "line_id": line["line_id"],
                "target_project_id": project_id, "target_type": "PROJECT",
                "quantity": str(quantity), "unit": "piece", "effective_on": day.isoformat(),
                "source_refs": [f"{tx_id}-ACCEPTED-ASSIGNMENT-{project_id}"],
                "status": "ACCEPTED",
            })
            references.append({
                "reference_id": f"{tx_id}-REFERENCE-{project_id}",
                "company_id": company_id, "project_id": project_id,
                "item_code": "SYN-MASONRY-UNIT", "unit": "piece",
                "baseline_kind": "APPROVED_PROCUREMENT_ALLOCATION",
                "quantity": str(50 if reallocated else quantity_limit),
                "valid_from": day.isoformat(),
                "source_refs": [f"{tx_id}-PROCUREMENT-{project_id}"],
                "acceptance_status": "ACCEPTED_SYNTHETIC_FIXTURE",
                "accepted_by": "SYNTHETIC_REVIEWER",
            })
        deliveries = [{
            "delivery_id": f"{tx_id}-DELIVERY", "transaction_id": tx_id,
            "item_code": "SYN-MASONRY-UNIT", "quantity": "100", "unit": "piece",
            "received_at": day.isoformat(), "source_refs": [f"{tx_id}-RECEIPT-SOURCE"],
            "status": "ACCEPTED_SYNTHETIC_FIXTURE",
        }]
    return TransactionInputs.model_validate({
        "case_id": case_id, "company_id": company_id, "case_version": case_version,
        "as_of": _instant(date(2026, 1, 10)),
        "transaction": {
            "transaction_id": tx_id, "buyer_company_id": company_id,
            "seller_company_id": seller_id,
            "invoice_observation_ids": [o["observation_id"] for o in observations],
            "project_id": f"{company_id}-P1", "economic_period": f"2025-{month:02d}",
            "source_coverage": "SYNTHETIC_STRUCTURED_SOURCES",
            "correlation_status": "LINKED_SYNTHETIC_EVENT", "canonical_revision": case_version,
        },
        "invoice_observations": observations, "documents": documents,
        "payments": payments, "payment_allocations": payment_allocations,
        "identity_mappings": mappings, "allocations": allocations,
        "quantity_references": references, "deliveries": deliveries,
    }).model_dump(mode="json", exclude_defaults=True, exclude_none=True)


def generate_screening_population(*, seed: int = DEFAULT_SEED,
                                  company_count: int = 40) -> dict:
    """Return 30–50 fictional companies and 12 linked monthly events each."""
    if not isinstance(seed, int) or not 30 <= company_count <= 50:
        raise ValueError("seed must be an integer and company_count must be 30..50")
    rng = Random(seed)
    prices = [10_000 + rng.randrange(0, 6) * 500 for _ in range(12)]
    companies = []
    transactions = []
    monthly_history = []
    for number in range(1, company_count + 1):
        company_id = f"SYN-C{number:03d}"
        companies.append({"company_id": company_id, "display_name": f"Synthetic Company {number:03d}",
                          "data_kind": "SYNTHETIC"})
        pattern = (number - 1) % PATTERN_COUNT
        for month, price in enumerate(prices, start=1):
            options = {}
            if pattern == 1 and month == 1:
                options["quantity_limit"] = 50
            elif pattern == 2 and month == 1:
                options["conflict"] = True
            elif pattern == 3:
                options.update(confirmed=False, counterpart=False)
            elif pattern == 4 and month == 1:
                options["payment_fraction"] = 2
            elif pattern == 5 and month == 1:
                options["quantity_limit"] = 50
            elif pattern == 6:
                options["counterpart"] = False
            elif pattern == 7 and month == 1:
                options["quantity_limit"] = 50
            elif pattern == 7 and month == 2:
                options["conflict"] = True
            current = _input(company_id, month, price, **options)
            revisions = [current]
            if pattern == 5 and month == 1:
                revisions.append(_input(company_id, month, price,
                                        reallocated=True, case_version=2))
            transactions.append({"transaction_id": current["transaction"]["transaction_id"],
                                 "company_id": company_id, "revisions": revisions})
            buyer_view = revisions[-1]["invoice_observations"][0]
            monthly_history.append({
                "company_id": company_id, "period": f"2025-{month:02d}",
                "transaction_ids": [current["transaction"]["transaction_id"]],
                "invoiced_purchases_millimes": buyer_view["gross_millimes"],
                "observed_settled_millimes": sum(
                    allocation["allocated_millimes"] for allocation in
                    revisions[-1].get("payment_allocations", [])),
                "declared_total_millimes": None,
                "declared_total_status": "NOT_SUPPLIED",
                "source_mode": "SYNTHETIC_STRUCTURED_ONLY",
            })
    return {"version": POPULATION_VERSION, "seed": seed,
            "source_mode": "SYNTHETIC_STRUCTURED_ONLY", "companies": companies,
            "transactions": transactions, "monthly_history": monthly_history}
