"""Queue triage (operational urgency) and clarification demo deadlines — lane A.

``triage_priority`` is NOT ``review_index``. The review index stays the deterministic,
evidence-supported documentary review priority computed by the checks engine; nothing
here reads or writes it except to echo it as the triage base. Triage answers a different
question: "which dossier needs the officer's attention first today?".

Transparent demo formula (formula ``triage-demo-1``; points are demo conventions, not
legal weights, and are shown to the officer as reason codes):

    triage_priority = min(100, base + sum(points of the operational signals present))
    base            = review_index (0 when unknown)

    REVIEW_FINDING_PRESENT               +0   an UNRESOLVED deterministic finding exists (explains the base)
    CLARIFICATION_PENDING                +10  a published clarification awaits the company's response
    CLARIFICATION_OVERDUE                +10  that response is past its DEMO service target
    REPEATED_UNANSWERED_CLARIFICATION    +10  two or more requests are past target without a response
    EVIDENCE_AWAITING_OFFICER_DECISION   +10  a company proposal waits for a human accept/reject
    ACTIVITY_GAP_NEEDS_REVIEW            +10  lane B signal ACTIVITY_GAP
    HISTORICAL_DATA_GAP_NEEDS_REVIEW     +10  lane B signal LATE_DOCUMENT_ACTIVITY or INSUFFICIENT_HISTORY
    TRANSACTION_INCONSISTENCY_NEEDS_REVIEW +10 lane B signal REPEATED_INVOICE_CONFLICT
    HISTORY_PATTERN_CHANGE_NEEDS_REVIEW  +5   lane B signal VOLUME_SPIKE, VOLUME_DROP,
                                              PAYMENT_PATTERN_CHANGE or COUNTERPARTY_CONCENTRATION_CHANGE
    (NO_SIGNIFICANT_CHANGE adds nothing; each triage reason counts once.)

Unanswered or overdue clarifications only add urgency: they never create a finding,
never change the review index and are never a fraud signal.
"""
from __future__ import annotations

from datetime import datetime

from boussla.contracts import (
    ClarificationDeadlineView, CompanyHistorySignal, EvidenceProposal, Finding, FindingStatus,
    HistorySignalCode, ProposalStatus, RequestStatus, RequestView, TriageAssessment,
)

FORMULA_VERSION = "triage-demo-1"
PENDING_STATUSES = (RequestStatus.PUBLISHED_IN_DEMO, RequestStatus.EXTENDED)

POINTS = {
    "REVIEW_FINDING_PRESENT": 0,
    "CLARIFICATION_PENDING": 10,
    "CLARIFICATION_OVERDUE": 10,
    "REPEATED_UNANSWERED_CLARIFICATION": 10,
    "EVIDENCE_AWAITING_OFFICER_DECISION": 10,
    "ACTIVITY_GAP_NEEDS_REVIEW": 10,
    "HISTORICAL_DATA_GAP_NEEDS_REVIEW": 10,
    "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW": 10,
    "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW": 5,
}
SIGNAL_REASON = {
    HistorySignalCode.ACTIVITY_GAP: "ACTIVITY_GAP_NEEDS_REVIEW",
    HistorySignalCode.LATE_DOCUMENT_ACTIVITY: "HISTORICAL_DATA_GAP_NEEDS_REVIEW",
    HistorySignalCode.INSUFFICIENT_HISTORY: "HISTORICAL_DATA_GAP_NEEDS_REVIEW",
    HistorySignalCode.REPEATED_INVOICE_CONFLICT: "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW",
    HistorySignalCode.VOLUME_SPIKE: "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW",
    HistorySignalCode.VOLUME_DROP: "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW",
    HistorySignalCode.PAYMENT_PATTERN_CHANGE: "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW",
    HistorySignalCode.COUNTERPARTY_CONCENTRATION_CHANGE: "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW",
}
SIGNAL_REASON_ORDER = ("ACTIVITY_GAP_NEEDS_REVIEW", "HISTORICAL_DATA_GAP_NEEDS_REVIEW",
                       "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW", "HISTORY_PATTERN_CHANGE_NEEDS_REVIEW")
ANOMALY_CODES = frozenset(SIGNAL_REASON) - {HistorySignalCode.INSUFFICIENT_HISTORY}


def clarification_deadlines(requests: list[RequestView] | tuple[RequestView, ...],
                            now: datetime) -> tuple[ClarificationDeadlineView, ...]:
    """Demo target status per published request. Only a request still awaiting the
    company's response can be overdue; overdue_days counts whole days past target."""
    out = []
    for rv in requests:
        req = rv.request
        if req.status is RequestStatus.DRAFT:
            continue
        overdue = (req.status in PENDING_STATUSES and req.target_response_at is not None
                   and now > req.target_response_at)
        days = (now - req.target_response_at).days if overdue else 0
        out.append(ClarificationDeadlineView(
            request_id=req.request_id, origin=req.origin, status=req.status,
            target_response_at=req.target_response_at, overdue=overdue, overdue_days=max(days, 0)))
    return tuple(out)


def assess_triage(*, case_id: str, case_version: int, review_index: int | None,
                  findings: tuple[Finding, ...], deadlines: tuple[ClarificationDeadlineView, ...],
                  proposals: list[EvidenceProposal] | tuple[EvidenceProposal, ...],
                  history_signals: tuple[CompanyHistorySignal, ...], now: datetime) -> TriageAssessment:
    """Deterministic triage from already-computed inputs (no clock, model or I/O here)."""
    reasons: list[str] = []
    if any(f.status is FindingStatus.UNRESOLVED for f in findings):
        reasons.append("REVIEW_FINDING_PRESENT")
    pending = [d for d in deadlines if d.status in PENDING_STATUSES]
    overdue = [d for d in pending if d.overdue]
    if pending:
        reasons.append("CLARIFICATION_PENDING")
    if overdue:
        reasons.append("CLARIFICATION_OVERDUE")
    if len(overdue) >= 2:
        reasons.append("REPEATED_UNANSWERED_CLARIFICATION")
    if any(p.status is ProposalStatus.AWAITING_HUMAN_REVIEW for p in proposals):
        reasons.append("EVIDENCE_AWAITING_OFFICER_DECISION")
    present = {SIGNAL_REASON[s.reason_code] for s in history_signals if s.reason_code in SIGNAL_REASON}
    reasons += [r for r in SIGNAL_REASON_ORDER if r in present]  # fixed order; each reason once
    base = review_index or 0
    components = {"REVIEW_INDEX_BASE": base, **{r: POINTS[r] for r in reasons}}
    priority = max(0, min(100, sum(components.values())))
    return TriageAssessment(case_id=case_id, case_version=case_version, triage_priority=priority,
                            review_index=review_index, reason_codes=tuple(reasons), components=components,
                            formula_version=FORMULA_VERSION, as_of=now)
