"""Derive per-cause progress from linked, versioned case facts.

An unlinked upload or answer never reduces the documentary review index.
"""

from __future__ import annotations

from boussla.contracts import Finding, FindingFamily, FindingStatus, ProposalStatus
from boussla.review_progress import ProgressEvidence


def derive_progress_evidence(findings: tuple[Finding, ...], facts: dict[str, list],
                             previous_snapshot: object | None) -> tuple[ProgressEvidence, ...]:
    requests = {v.request.request_id: v.request for v in facts.get("request", ())}
    proposals = {p.source_response_id: p for p in facts.get("proposal", ()) if p.source_response_id}
    documents = {d.document_id for d in facts.get("document", ())}
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
            if request is None or not response.answers:
                continue
            proposal = proposals.get(response.response_id)
            scoped_proposal = (proposal is not None
                               and proposal.transaction_id == transaction_id
                               and family is FindingFamily.QUANTITY)
            scoped_question = (family is FindingFamily.QUANTITY
                               and "Q-PROJECT-ALLOCATION" in response.answers
                               and bool(set(request.fact_ids) & refs))
            scoped_reason = bool(reason_codes & set(request.reason_codes))
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
        result.append(ProgressEvidence(
            transaction_id=transaction_id, family=family,
            response_id=response.response_id, document_id=document_id,
            proposal_id=proposal.proposal_id if proposal else None,
            officer_accepted=proposal is not None and proposal.status is ProposalStatus.ACCEPTED,
            rejected=proposal is not None and proposal.status is ProposalStatus.REJECTED,
            prior_raw_contribution=previous.raw_contribution if previous is not None else None,
        ))
    return tuple(result)
