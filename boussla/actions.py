"""Deterministic officer next steps from real case state; no side effects."""
from boussla.contracts import RecommendedAction


def recommend_actions(view):
    actions = []
    def add(kind,title,priority,reason,causes=(),docs=(),sources=(),status="OPEN"):
        sources = tuple(x for x in sources if x)
        unique = tuple(sorted(set(causes)))
        actions.append(RecommendedAction(action_id=f"ACT:{kind}:{':'.join(unique or tuple(sources)[:1]) or view.case_id}",
            kind=kind,title_fr=title,priority=priority,reason=reason,source_causes=unique,
            required_documents=tuple(sorted(set(docs))),source_ids=tuple(sorted(set(sources))),status=status))
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
    return tuple(sorted(actions,key=lambda a:(a.priority,a.kind,a.action_id)))[:12]
