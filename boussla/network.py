"""Typed, source-attributed network projection from authorized case facts."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from pydantic import Field
from boussla.contracts import Contract, InvoiceObservation

RULE_VERSION = "case-network-1"


class NetworkNode(Contract):
    node_id: str
    kind: str
    label: str
    case_ids: tuple[str, ...]
    attributes: dict[str, str] = Field(default_factory=dict)


class NetworkEdge(Contract):
    edge_id: str
    source: str
    target: str
    kind: str
    case_id: str
    source_ids: tuple[str, ...]
    provenance_status: str


class NetworkView(Contract):
    scope: str
    scope_id: str | None = None
    nodes: tuple[NetworkNode, ...]
    edges: tuple[NetworkEdge, ...]
    calculated_at: datetime
    rule_version: str = RULE_VERSION
    note_fr: str = "Relations observées dans les dossiers autorisés ; aucun signal de fraude."


def build_network(cases: Iterable[tuple[str, dict[str, list]]], *, names: dict[str, str],
                  scope: str = "ALL", scope_id: str | None = None) -> NetworkView:
    nodes: dict[str, NetworkNode] = {}
    edges: dict[str, NetworkEdge] = {}

    def node(kind: str, identifier: str, label: str, case_id: str, **attributes: str) -> str:
        node_id = f"{kind.lower()}:{identifier}"
        existing = nodes.get(node_id)
        case_ids = tuple(sorted(set((*existing.case_ids, case_id)))) if existing else (case_id,)
        nodes[node_id] = NetworkNode(node_id=node_id, kind=kind, label=label,
                                     case_ids=case_ids, attributes=attributes or (existing.attributes if existing else {}))
        return node_id

    def edge(source: str, target: str, kind: str, case_id: str, source_ids: tuple[str, ...],
             provenance: str) -> None:
        if source not in nodes or target not in nodes:
            return
        edge_id = f"{case_id}:{kind}:{source}:{target}"
        existing = edges.get(edge_id)
        evidence = tuple(sorted(set((*existing.source_ids, *source_ids)))) if existing else source_ids
        edges[edge_id] = NetworkEdge(edge_id=edge_id, source=source, target=target, kind=kind,
                                     case_id=case_id, source_ids=evidence, provenance_status=provenance)

    for case_id, facts in cases:
        case_node = node("CASE", case_id, case_id, case_id)
        transactions = {item.transaction_id: item for item in facts["transaction"]}
        observations: dict[str, InvoiceObservation] = {item.observation_id: item for item in facts["invoice_observation"]}
        documents = {item.document_id: item for item in facts["document"]}
        payments = {item.payment_id: item for item in facts["payment"]}
        projects = {item.project_id: item for item in facts["project"]}
        for project in projects.values():
            project_node = node("PROJECT", project.project_id, project.label, case_id)
            edge(project_node, case_node, "RELATED_TO", case_id, (project.project_id,), "CANONICAL_PROJECT")
        for document in documents.values():
            doc_node = node("DOCUMENT", document.document_id, document.original_filename, case_id,
                            received_at=document.received_at.isoformat())
            edge(doc_node, case_node, "RELATED_TO", case_id, (document.document_id,), "RECORDED_DOCUMENT")
        for transaction in transactions.values():
            tx_node = node("TRANSACTION", transaction.transaction_id, transaction.transaction_id, case_id,
                           economic_period=transaction.economic_period)
            edge(tx_node, case_node, "RELATED_TO", case_id, (transaction.transaction_id,), "CANONICAL_TRANSACTION")
            buyer = node("COMPANY", transaction.buyer_company_id,
                         names.get(transaction.buyer_company_id, transaction.buyer_company_id), case_id)
            edge(buyer, tx_node, "RELATED_TO", case_id, (transaction.transaction_id,), "CANONICAL_TRANSACTION")
            if transaction.seller_company_id:
                seller = node("COMPANY", transaction.seller_company_id,
                              names.get(transaction.seller_company_id, transaction.seller_company_id), case_id)
                edge(seller, buyer, "SELLS_TO", case_id, (transaction.transaction_id,), "CANONICAL_TRANSACTION")
                edge(buyer, seller, "BUYS_FROM", case_id, (transaction.transaction_id,), "CANONICAL_TRANSACTION")
            if transaction.project_id and transaction.project_id in projects:
                edge(tx_node, f"project:{transaction.project_id}", "BELONGS_TO_PROJECT", case_id,
                     (transaction.transaction_id, transaction.project_id), "CANONICAL_TRANSACTION")
            for observation_id in transaction.invoice_observation_ids:
                observation = observations.get(observation_id)
                if observation is None:
                    continue
                invoice_node = node("INVOICE", observation.observation_id, observation.invoice_number, case_id,
                                    issued_on=observation.issued_on.isoformat(),
                                    gross_millimes=str(observation.gross_millimes), currency=observation.currency)
                edge(invoice_node, tx_node, "RELATED_TO", case_id,
                     (observation.observation_id, transaction.transaction_id), "RECORDED_OBSERVATION")
                if observation.document_id in documents:
                    edge(invoice_node, f"document:{observation.document_id}", "JUSTIFIED_BY", case_id,
                         (observation.observation_id, observation.document_id), "RECORDED_OBSERVATION")
                if observation.issuer_company_id:
                    issuer = node("COMPANY", observation.issuer_company_id,
                                  names.get(observation.issuer_company_id, observation.issuer_company_id), case_id)
                    edge(issuer, invoice_node, "ISSUED", case_id,
                         (observation.observation_id, observation.document_id), "RECORDED_OBSERVATION")
                if observation.buyer_company_id:
                    receiver = node("COMPANY", observation.buyer_company_id,
                                    names.get(observation.buyer_company_id, observation.buyer_company_id), case_id)
                    edge(receiver, invoice_node, "RECEIVED", case_id,
                         (observation.observation_id, observation.document_id), "RECORDED_OBSERVATION")
        for payment in payments.values():
            payment_node = node("PAYMENT", payment.payment_id, payment.payment_id, case_id,
                                amount_millimes=str(payment.amount_millimes), currency=payment.currency,
                                occurred_at=payment.occurred_at.isoformat())
            edge(payment_node, case_node, "RELATED_TO", case_id,
                 (payment.source_record_id, payment.payment_id), "RECORDED_PAYMENT")
        for allocation in facts["payment_allocation"]:
            payment = payments.get(allocation.payment_id)
            if payment is None or allocation.transaction_id not in transactions:
                continue
            payment_node = node("PAYMENT", payment.payment_id, payment.payment_id, case_id,
                                amount_millimes=str(payment.amount_millimes), currency=payment.currency,
                                occurred_at=payment.occurred_at.isoformat())
            edge(payment_node, f"transaction:{allocation.transaction_id}", "PAID", case_id,
                 (payment.source_record_id, payment.payment_id, allocation.transaction_id), "ACCEPTED_ALLOCATION")
        for delivery in facts["delivery"]:
            if delivery.transaction_id not in transactions:
                continue
            delivery_node = node("DELIVERY", delivery.delivery_id, delivery.delivery_id, case_id,
                                 quantity=delivery.quantity, unit=delivery.unit)
            edge(delivery_node, f"transaction:{delivery.transaction_id}", "RELATED_TO", case_id,
                 (delivery.delivery_id, *delivery.source_refs), "RECORDED_DELIVERY")
    return NetworkView(scope=scope, scope_id=scope_id, nodes=tuple(sorted(nodes.values(), key=lambda item: item.node_id)),
                       edges=tuple(sorted(edges.values(), key=lambda item: item.edge_id)),
                       calculated_at=datetime.now(timezone.utc))
