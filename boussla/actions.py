"""Deterministic officer next steps from real case state; no side effects."""
from boussla.contracts import RecommendedAction

RULE_VERSION = "recommended-actions-2"


def recommend_actions(view):
    actions = []
    def add(kind,title,priority,reason,causes=(),docs=(),sources=(),status="OPEN"):
        sources = tuple(x for x in sources if x)
        unique = tuple(sorted(set(causes)))
        actions.append(RecommendedAction(action_id=f"ACT:{kind}:{':'.join(unique or tuple(sources)[:1]) or view.case_id}",
            kind=kind,title_fr=title,priority=priority,reason=reason,source_causes=unique,
            required_documents=tuple(sorted(set(docs))),source_ids=tuple(sorted(set(sources))),status=status,
            rule_version=RULE_VERSION))
    causes = tuple(view.score.cause_progress) if view.score else ()
    by_tx = {}
    for cause in causes:
        by_tx.setdefault(cause.transaction_id,[]).append(cause)
    pending = {p.transaction_id for p in view.proposals if p.status.value == "AWAITING_HUMAN_REVIEW"}
    for proposal in view.proposals:
        if proposal.status.value == "AWAITING_HUMAN_REVIEW":
            related = tuple(c.cause_id for c in by_tx.get(proposal.transaction_id,()) if c.family.value == "QUANTITY")
            coherent = any(c.stage.value == "EVIDENCE_COHERENT" for c in by_tx.get(proposal.transaction_id,()))
            add("VALIDATE_CAUSE" if coherent else "REVIEW_EVIDENCE",
                (f"Valider la cause de {proposal.transaction_id}" if coherent else
                 f"Examiner le justificatif de {proposal.transaction_id}"),1,
                "Pièce cohérente ; décision humaine requise." if coherent else
                "Proposition d’affectation en attente d’une décision de l’agent.",related,
                ("ALLOCATION_REFERENCE",) if not proposal.source_document_id else (),
                (proposal.proposal_id,proposal.source_document_id or ""))
    reviewed_documents = {p.source_document_id for p in view.proposals if p.status.value in ("ACCEPTED","REJECTED")}
    for doc in view.documents:
        analysis = doc.analysis
        if analysis is None or doc.document.document_id in reviewed_documents:
            continue
        linked = tuple(c for c in analysis.linked_cause_ids if c in {x.cause_id for x in causes})
        priority = 1 if any(c.status == "FAIL" for c in analysis.checks) else 2
        add("REVIEW_DOCUMENT",f"Vérifier la pièce {doc.document.document_id}",priority,
            "Analyse documentaire disponible ; authenticité et pertinence à confirmer.",linked,(),
            (doc.document.document_id,))
    pending_requests = [r for r in view.requests if r.request.status.value in ("PUBLISHED_IN_DEMO","EXTENDED")]
    for request in pending_requests:
        scoped = {tx for q in request.questions for tx in q.related_fact_ids}
        related = tuple(c.cause_id for tx in scoped for c in by_tx.get(tx,()))
        overdue = any(d.request_id == request.request.request_id and d.overdue for d in view.clarification_deadlines)
        add("ESCALATE" if overdue else "WAIT_RESPONSE",
            "Relancer la demande de précision" if overdue else "Attendre la réponse de l’entreprise",
            2 if overdue else 4,"Date cible de démonstration dépassée." if overdue else
            "Une demande est déjà publiée ; attendre avant une nouvelle question.",related,(),
            (request.request.request_id,),"OPEN" if overdue else "WAITING")
    waiting_tx = {tx for r in pending_requests for q in r.questions for tx in q.related_fact_ids}
    for cause in causes:
        if cause.transaction_id in pending or cause.transaction_id in waiting_tx:
            continue
        if cause.stage.value == "RESOLVED":
            continue
        if cause.stage.value == "EVIDENCE_COHERENT":
            add("VALIDATE_CAUSE",f"Valider la cause {cause.transaction_id} — {cause.family.value}",1,
                "Pièce cohérente, amélioration encore provisoire ; décision humaine requise.",
                (cause.cause_id,),(),cause.source_ids)
        elif cause.stage.value == "EVIDENCE_RECEIVED":
            add("REVIEW_EVIDENCE",f"Examiner la preuve liée à {cause.transaction_id}",2,
                "Pièce reçue, cohérence ou source encore non confirmée.",(cause.cause_id,),(),cause.source_ids)
        elif cause.stage.value == "EXPLANATION_RECEIVED":
            add("REQUEST_DOCUMENT",f"Demander une pièce pour {cause.transaction_id}",3,
                "Réponse reçue sans pièce liée et confirmée.",(cause.cause_id,),
                {"QUANTITY":("ALLOCATION_REFERENCE",),"COUNTERPARTY":("DELIVERY_RECORD",),
                 "SETTLEMENT":("PAYMENT_RECORD",)}.get(cause.family.value,()),cause.source_ids)
        elif cause.reason_code == "EVIDENCE_REJECTED":
            add("REQUEST_DOCUMENT",f"Demander une autre pièce pour {cause.transaction_id}",2,
                "La preuve précédente a été rejetée ; la cause reste ouverte.",(cause.cause_id,),
                {"QUANTITY":("ALLOCATION_REFERENCE",),"COUNTERPARTY":("DELIVERY_RECORD",),
                 "SETTLEMENT":("PAYMENT_RECORD",)}.get(cause.family.value,()),cause.source_ids)
        else:
            add("REQUEST_EXPLANATION",f"Demander une explication pour {cause.transaction_id}",3,
                "Cause détectée sans réponse liée.",(cause.cause_id,),(),cause.source_ids)
    active = tuple(sorted(actions, key=lambda a: (a.priority, a.kind, a.action_id)))[:12]
    completed = []
    for proposal in view.proposals:
        if proposal.status.value not in ("ACCEPTED", "REJECTED") or proposal.decided_at is None:
            continue
        causes = tuple(sorted(c.cause_id for c in by_tx.get(proposal.transaction_id, ())
                              if c.family.value == "QUANTITY"))
        kind = "VALIDATE_CAUSE" if proposal.status.value == "ACCEPTED" else "REVIEW_EVIDENCE"
        completed.append((proposal.decided_at, RecommendedAction(
            action_id=f"ACT:{kind}:{':'.join(causes) or proposal.proposal_id}", kind=kind,
            title_fr=("Validation de la cause terminée" if kind == "VALIDATE_CAUSE" else
                      "Examen de la preuve terminé"), priority=5,
            reason=("Proposition acceptée par l’agent." if kind == "VALIDATE_CAUSE" else
                    "Proposition rejetée par l’agent ; une autre preuve peut être demandée."),
            source_causes=causes, source_ids=(proposal.proposal_id,), status="COMPLETED",
            rule_version=RULE_VERSION)))
        if proposal.source_document_id:
            completed.append((proposal.decided_at, RecommendedAction(
                action_id=f"ACT:REVIEW_DOCUMENT:{proposal.source_document_id}", kind="REVIEW_DOCUMENT",
                title_fr=f"Examen de la pièce {proposal.source_document_id} terminé", priority=5,
                reason="Décision humaine enregistrée sur une proposition liée à cette pièce.",
                source_causes=causes, source_ids=(proposal.source_document_id, proposal.proposal_id),
                status="COMPLETED", rule_version=RULE_VERSION)))
    for request in view.requests:
        if request.request.status.value != "RESPONDED":
            continue
        responses = [r for r in view.responses if r.request_id == request.request.request_id]
        if not responses:
            continue
        response = max(responses, key=lambda r: r.submitted_at)
        completed.append((response.submitted_at, RecommendedAction(
            action_id=f"ACT:WAIT_RESPONSE:{request.request.request_id}", kind="WAIT_RESPONSE",
            title_fr="Réponse de l’entreprise reçue", priority=5,
            reason="La demande publiée a reçu une réponse attribuée.",
            source_ids=(request.request.request_id, response.response_id), status="COMPLETED",
            rule_version=RULE_VERSION)))
    recent = [action for _, action in sorted(completed, key=lambda pair: pair[0], reverse=True)[:3]]
    return active + tuple(recent)
