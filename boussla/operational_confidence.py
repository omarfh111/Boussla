"""Four normalized, source-backed operational confidence dimensions."""

from __future__ import annotations

from datetime import datetime
from calendar import monthrange
from decimal import Decimal, ROUND_HALF_UP

from boussla.contracts import (ClarificationResponse, CompanyHistorySignal, EvidenceProposal,
                               HistorySignalCode, OperationalConfidence, OperationalConfidenceFactor,
                               ProposalStatus, RequestStatus, RequestView)
from boussla.review_progress import ProgressEvidence

WEIGHTS = {"TIMELINESS": 30, "ANSWER_COHERENCE": 25,
           "EVIDENCE_CORROBORATION": 25, "HISTORICAL_STABILITY": 20}


def _decimal_str(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP).normalize(), "f")


def confidence_window_start(as_of: datetime) -> datetime:
    return as_of.replace(year=as_of.year - 1,
                         day=min(as_of.day, monthrange(as_of.year - 1, as_of.month)[1]))


def calculate_operational_confidence(
    requests: tuple[RequestView, ...], responses: tuple[ClarificationResponse, ...],
    proposals: tuple[EvidenceProposal, ...], history_signals: tuple[CompanyHistorySignal, ...],
    as_of: datetime, progress_evidence: tuple[ProgressEvidence, ...] = (),
    covered_transaction_ids: tuple[str, ...] = (), conflicted_transaction_ids: tuple[str, ...] = (),
) -> OperationalConfidence:
    """Calculate at an explicit cutoff; unknown dimensions never earn points.

    The numerator/denominator for each eligible dimension is persisted in the
    officer response. Contributions are percentage points after renormalizing
    only the dimensions whose denominator is nonzero.
    """
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    window_start = confidence_window_start(as_of)
    published = tuple(v.request for v in requests if v.request.status is not RequestStatus.DRAFT
                      and (v.request.published_at is None or v.request.published_at <= as_of))
    request_ids_in_scope = {r.request_id for r in published}
    response_by_request = {r.request_id: r for r in responses
                           if window_start <= r.submitted_at <= as_of and r.request_id in request_ids_in_scope}
    dimensions: list[tuple[str, int, int, tuple[str, ...], tuple[str, ...], str]] = []

    eligible_requests = tuple(r for r in published if r.target_response_at is not None
                              and (r.target_response_at >= window_start or r.request_id in response_by_request)
                              and (r.target_response_at <= as_of or r.request_id in response_by_request))
    if eligible_requests:
        timely = sum(response_by_request.get(r.request_id) is not None
                     and response_by_request[r.request_id].submitted_at <= r.target_response_at
                     for r in eligible_requests)
        request_ids = tuple(dict.fromkeys(x for r in eligible_requests
                                          for x in (r.request_id,
                                                    response_by_request[r.request_id].response_id
                                                    if r.request_id in response_by_request else None) if x))
        reasons = tuple(sorted({"TIMELY_RESPONSE" if r.request_id in response_by_request
                                and response_by_request[r.request_id].submitted_at <= r.target_response_at
                                else "LATE_RESPONSE" if r.request_id in response_by_request
                                else "UNANSWERED_REQUEST" for r in eligible_requests}))
        dimensions.append(("TIMELINESS", timely, len(eligible_requests), reasons, request_ids,
                           "Réponses dans la cible de démonstration parmi les demandes arrivées à échéance ou répondues."))

    answer_ids = {r.response_id for r in response_by_request.values()}
    verifiable: dict[str, list[ProgressEvidence]] = {}
    for evidence in progress_evidence:
        if evidence.response_id in answer_ids and evidence.document_id is not None \
                and (evidence.technically_consistent or evidence.contradiction_reason):
            verifiable.setdefault(evidence.response_id, []).append(evidence)
    if verifiable:
        consistent = sum(all(e.technically_consistent and not e.contradiction_reason for e in items)
                         for items in verifiable.values())
        refs = tuple(sorted({x for items in verifiable.values() for e in items
                             for x in (e.response_id, e.document_id, e.proposal_id) if x}))
        reasons = tuple(sorted({e.contradiction_reason or "DOCUMENT_COHERENT" for items in verifiable.values()
                                for e in items}))
        dimensions.append(("ANSWER_COHERENCE", consistent, len(verifiable), reasons, refs,
                           "Réponses corroborées parmi celles vérifiables par des champs documentaires sourcés."))

    response_dates = {r.response_id: r.submitted_at for r in responses}
    judged = tuple(p for p in proposals if p.source_document_id is not None
                   and p.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED)
                   and (p.decided_at or response_dates.get(p.source_response_id)) is not None
                   and window_start <= (p.decided_at or response_dates[p.source_response_id]) <= as_of)
    if judged:
        accepted = sum(p.status is ProposalStatus.ACCEPTED for p in judged)
        refs = tuple(sorted({x for p in judged for x in (p.proposal_id, p.source_document_id) if x}))
        reasons = tuple(sorted({"ACCEPTED_PROOF" if p.status is ProposalStatus.ACCEPTED else "REJECTED_PROOF"
                                for p in judged}))
        dimensions.append(("EVIDENCE_CORROBORATION", accepted, len(judged), reasons, refs,
                           "Pièces acceptées parmi les propositions documentaires examinées par l’agent."))

    covered = set(covered_transaction_ids)
    if covered:
        conflicted = covered & set(conflicted_transaction_ids)
        historical_refs = {s.signal_id for s in history_signals
                           if s.reason_code is HistorySignalCode.REPEATED_INVOICE_CONFLICT}
        refs = tuple(sorted(covered | historical_refs))
        dimensions.append(("HISTORICAL_STABILITY", len(covered) - len(conflicted), len(covered),
                           ("REPEATED_INVOICE_CONFLICT",) if conflicted else ("NO_REPEATED_CONFLICT",), refs,
                           "Transactions couvertes sans conflit de facture répété parmi les transactions couvertes."))

    response_requests = {r.response_id: r.request_id for r in response_by_request.values()}
    distinct_requests = {r.request_id for r in eligible_requests} | {response_requests[r] for r in verifiable}
    distinct_documents = {p.source_document_id for p in judged}
    count = len(distinct_requests) + len(distinct_documents) + len(covered)
    quality = "INSUFFICIENT_DATA" if count < 3 else "LIMITED_DATA" if count < 10 else "OBSERVED"
    sample = dict(window_start=window_start, sample_size=count,
                  request_count=len(distinct_requests), document_count=len(distinct_documents),
                  history_transaction_count=len(covered), data_quality=quality,
                  sample_note_fr=f"{len(distinct_requests)} demandes, {len(distinct_documents)} pièces examinées et "
                                 f"{len(covered)} transactions historiques sur les 12 derniers mois. "
                                 + (f"Données limitées — {count} éléments distincts seulement." if count < 10
                                    else "Observations attribuées ; aucune certitude statistique revendiquée."))
    if count < 3:
        return OperationalConfidence(index=None, status="INSUFFICIENT_DATA", as_of=as_of,
                                     eligible_observations=count, **sample)

    active_weight = sum(WEIGHTS[code] for code, *_ in dimensions)
    factors = []
    raw = Decimal(0)
    for code, numerator, denominator, reasons, refs, explanation in dimensions:
        effective = Decimal(100) * WEIGHTS[code] / active_weight
        contribution = effective * numerator / denominator
        raw += contribution
        factors.append(OperationalConfidenceFactor(
            code=code, numerator=numerator, denominator=denominator,
            nominal_weight=WEIGHTS[code], effective_weight=_decimal_str(effective),
            weighted_contribution=_decimal_str(contribution), reason_codes=reasons,
            source_ids=refs, explanation_fr=explanation))
    index = int(raw.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return OperationalConfidence(index=index, status="AVAILABLE", as_of=as_of,
                                 factors=tuple(factors), eligible_observations=count, **sample)
