"""Derive per-cause progress from linked, versioned case facts.

An unlinked upload or answer never reduces the documentary review index.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from boussla.contracts import Finding, FindingFamily, FindingStatus, ProposalStatus
from boussla.review_progress import ProgressEvidence

CAUSE_QUESTIONS = {
    FindingFamily.QUANTITY: frozenset({"Q-PROJECT-ALLOCATION", "Q-STOCK"}),
    FindingFamily.COUNTERPARTY: frozenset({"Q-COUNTERPART-RECORD"}),
    FindingFamily.SETTLEMENT: frozenset(),
}


def derive_progress_evidence(findings: tuple[Finding, ...], facts: dict[str, list],
                             previous_snapshot: object | None) -> tuple[ProgressEvidence, ...]:
    requests = {v.request.request_id: v.request for v in facts.get("request", ())}
    proposals = {p.source_response_id: p for p in facts.get("proposal", ()) if p.source_response_id}
    documents = {d.document_id for d in facts.get("document", ())}
    extractions = {e.document_id: e for e in facts.get("extraction", ())}
    prior_causes = {
        (c.transaction_id, c.family): c
        for c in getattr(previous_snapshot, "cause_progress", ())
    }
    grouped: dict[tuple[str, FindingFamily], list[Finding]] = {}
    for finding in findings:
        if finding.status in (FindingStatus.UNRESOLVED, FindingStatus.EXPLAINED):
            grouped.setdefault((finding.transaction_id, finding.family), []).append(finding)
    result: list[ProgressEvidence] = []
    for (transaction_id, family), related in grouped.items():
        refs = {ref.source_record_id or ref.document_id
                for finding in related for ref in finding.evidence_refs}
        reason_codes = {finding.reason_code for finding in related if finding.reason_code}
        matches = []
        for response in facts.get("response", ()):
            request = requests.get(response.request_id)
            if request is None:
                continue
            proposal = proposals.get(response.response_id)
            scoped_proposal = (proposal is not None
                               and proposal.transaction_id == transaction_id
                               and family is FindingFamily.QUANTITY)
            scoped_question = (family is FindingFamily.QUANTITY
                               and "Q-PROJECT-ALLOCATION" in response.answers
                               and bool(set(request.fact_ids) & refs))
            scoped_reason = (bool(reason_codes & set(request.reason_codes))
                             and bool(set(response.answers) & CAUSE_QUESTIONS[family]))
            if not (scoped_proposal or scoped_question or scoped_reason):
                continue
            document_id = next((d for d in response.document_ids if d in documents), None)
            if proposal is not None and scoped_proposal and proposal.source_document_id in documents:
                document_id = proposal.source_document_id
            matches.append((response, proposal if scoped_proposal else None, document_id))
        if not matches:
            continue
        response, proposal, document_id = max(matches, key=lambda item: item[0].submitted_at)
        previous = prior_causes.get((transaction_id, family))
        coherence = _allocation_coherence(proposal, document_id, extractions.get(document_id))
        result.append(ProgressEvidence(
            transaction_id=transaction_id, family=family,
            response_id=response.response_id, document_id=document_id,
            proposal_id=proposal.proposal_id if proposal else None,
            officer_accepted=proposal is not None and proposal.status is ProposalStatus.ACCEPTED,
            rejected=proposal is not None and proposal.status is ProposalStatus.REJECTED,
            technically_consistent=coherence is True,
            contradiction_reason="DOCUMENT_ALLOCATION_CONTRADICTION" if coherence is False else None,
            prior_raw_contribution=previous.raw_contribution if previous is not None else None,
        ))
    return tuple(result)


def _allocation_coherence(proposal, document_id: str | None, extraction) -> bool | None:
    """Only complete, source-backed and confirmed allocation fields can change a stage."""
    if proposal is None or document_id is None or extraction is None or extraction.status != "CONFIRMED":
        return None
    backed = {}
    for candidate in extraction.candidates:
        if candidate.normalized_value is None or candidate.raw_value is None:
            continue
        if any(ref.document_id == document_id and ref.page is not None and ref.exact_text
               and candidate.raw_value in ref.exact_text for ref in candidate.evidence_refs):
            backed[candidate.field_name] = candidate.normalized_value
    expected = {"allocation.transaction_id": proposal.transaction_id,
                "allocation.line_id": proposal.line_id}
    expected.update({f"allocation.{change.target_project_id}.quantity": change.new_quantity
                     for change in proposal.changes if change.target_project_id})
    if not set(expected) <= set(backed):
        return None
    for field, value in expected.items():
        actual = backed[field]
        if field.endswith(".quantity"):
            try:
                if Decimal(actual) != Decimal(value):
                    return False
            except InvalidOperation:
                return False
        elif actual != value:
            return False
    return True
