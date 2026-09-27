"""Explainable operational trust, scoped to observed interactions, not fraud risk."""

from __future__ import annotations

from datetime import datetime

from boussla.contracts import (CauseProgress, ClarificationResponse, CompanyHistorySignal, EvidenceProposal,
                               HistorySignalCode, OperationalConfidence, OperationalConfidenceFactor,
                               ProgressStage, ProposalStatus, RequestStatus, RequestView)


def calculate_operational_confidence(
    requests: tuple[RequestView, ...], responses: tuple[ClarificationResponse, ...],
    proposals: tuple[EvidenceProposal, ...], history_signals: tuple[CompanyHistorySignal, ...],
    as_of: datetime, cause_progress: tuple[CauseProgress, ...] = (),
) -> OperationalConfidence:
    """Read-time indicator. Two attributable observations are needed for a number.

    A published request counts as one observation, and a reviewed or pending
    proposal as another. Recalculation from current facts makes every factor
    reversible when a response arrives or a proposal changes state.
    """
    published = tuple(r.request for r in requests if r.request.status is not RequestStatus.DRAFT
                      and (r.request.published_at is None or r.request.published_at <= as_of))
    response_by_request = {r.request_id: r for r in responses if r.submitted_at <= as_of}
    relevant_proposals = tuple(p for p in proposals if p.status is not ProposalStatus.SUPERSEDED)
    count = len(published) + len(relevant_proposals)
    if count < 2:
        return OperationalConfidence(status="INSUFFICIENT_DATA", observation_count=count)

    factors: list[OperationalConfidenceFactor] = []
    for request in published:
        response = response_by_request.get(request.request_id)
        if response is not None:
            timely = request.target_response_at is None or response.submitted_at <= request.target_response_at
            factors.append(OperationalConfidenceFactor(
                code="TIMELY_RESPONSE" if timely else "LATE_RESPONSE",
                contribution=10 if timely else -5,
                source_ids=(request.request_id, response.response_id),
                explanation_fr="Réponse reçue dans le délai indicatif." if timely
                else "Réponse reçue après le délai indicatif."))
        elif request.status in (RequestStatus.PUBLISHED_IN_DEMO, RequestStatus.EXTENDED) \
                and request.target_response_at is not None and request.target_response_at < as_of:
            factors.append(OperationalConfidenceFactor(
                code="UNANSWERED_REQUEST", contribution=-10, source_ids=(request.request_id,),
                explanation_fr="Demande restée sans réponse après le délai indicatif."))
    for proposal in relevant_proposals:
        if proposal.status in (ProposalStatus.ACCEPTED, ProposalStatus.REJECTED):
            accepted = proposal.status is ProposalStatus.ACCEPTED
            factors.append(OperationalConfidenceFactor(
                code="ACCEPTED_PROOF" if accepted else "REJECTED_PROOF",
                contribution=10 if accepted else -15, source_ids=(proposal.proposal_id,),
                explanation_fr="Pièce ou proposition acceptée par l’agent." if accepted
                else "Pièce ou proposition rejetée par l’agent."))
    repeated = tuple(s.signal_id for s in history_signals
                     if s.reason_code is HistorySignalCode.REPEATED_INVOICE_CONFLICT)
    if repeated:
        factors.append(OperationalConfidenceFactor(
            code="REPEATED_ANOMALY", contribution=-10, source_ids=tuple(sorted(set(repeated))),
            explanation_fr="Incohérences répétées dans l’historique couvert."))
    stable = tuple(s.signal_id for s in history_signals
                   if s.reason_code is HistorySignalCode.NO_SIGNIFICANT_CHANGE)
    has_historical_deviation = any(s.reason_code not in (HistorySignalCode.NO_SIGNIFICANT_CHANGE,
                                                          HistorySignalCode.INSUFFICIENT_HISTORY)
                                   for s in history_signals)
    if stable and not has_historical_deviation:
        factors.append(OperationalConfidenceFactor(
            code="HISTORY_STABILITY", contribution=5, source_ids=tuple(sorted(set(stable))),
            explanation_fr="Aucune variation significative dans l’historique couvert."))
    for cause in cause_progress:
        if cause.reason_code == "DOCUMENT_ALLOCATION_CONTRADICTION":
            factors.append(OperationalConfidenceFactor(
                code="DOCUMENT_CONTRADICTORY", contribution=-15, source_ids=cause.source_ids,
                explanation_fr="Nouvelle pièce contradictoire avec l’affectation proposée."))
        elif cause.stage is ProgressStage.EVIDENCE_COHERENT:
            factors.append(OperationalConfidenceFactor(
                code="DOCUMENT_COHERENT", contribution=5, source_ids=cause.source_ids,
                explanation_fr="Pièce vérifiée et cohérente avec l’affectation proposée (validation encore requise)."))

    raw = 70 + sum(f.contribution for f in factors)
    return OperationalConfidence(index=max(0, min(100, raw)), uncapped_index=raw, status="AVAILABLE",
                                 factors=tuple(factors), observation_count=count)
