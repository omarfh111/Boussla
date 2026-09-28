"""Role and enterprise scope — lane A. Checked at every service entry.

This is LOCAL ROLE SIMULATION, not authentication. The UI may pass an
``Actor``, but the service never trusts its role/company/assignments: it
re-resolves the actor from the server-side roster and rejects any mismatch.
Scope is never derived from an uploaded MF, a document field or model output.
"""
from __future__ import annotations

from dataclasses import dataclass

from boussla.contracts import Actor, BousslaError, ErrorCode, Role

DEMO_BANNER_FR = "Simulation de rôles locale — pas une authentification de production."

# action -> roles allowed to perform it
POLICY: dict[str, frozenset[Role]] = {
    "create_case": frozenset({Role.COMPANY}),
    "upload_document": frozenset({Role.COMPANY, Role.OFFICER}),
    "confirm_transcription": frozenset({Role.COMPANY}),
    "submit_context": frozenset({Role.COMPANY}),
    "start_analysis": frozenset({Role.COMPANY, Role.OFFICER}),
    "answer_questions": frozenset({Role.COMPANY}),
    "get_case": frozenset({Role.COMPANY, Role.OFFICER}),
    "list_queue": frozenset({Role.OFFICER}),
    "prepare_clarification": frozenset({Role.OFFICER}),
    "publish_clarification": frozenset({Role.OFFICER}),
    "submit_response": frozenset({Role.COMPANY}),
    "accept_evidence": frozenset({Role.OFFICER}),
    "reject_evidence": frozenset({Role.OFFICER}),
    "get_history": frozenset({Role.COMPANY, Role.OFFICER}),
    "get_network": frozenset({Role.OFFICER}),
    "ask_investigation": frozenset({Role.OFFICER}),
    "export_dossier": frozenset({Role.OFFICER}),
    "reset_demo": frozenset({Role.DEMO_OPERATOR}),
    # Synthetic data administration: local demo operator only (never COMPANY or OFFICER).
    "admin_list_enterprises": frozenset({Role.DEMO_OPERATOR}),
    "admin_seed_portfolio": frozenset({Role.DEMO_OPERATOR}),
    "admin_reset_portfolio": frozenset({Role.DEMO_OPERATOR}),
    "admin_add_enterprise": frozenset({Role.DEMO_OPERATOR}),
    "admin_delete_enterprise": frozenset({Role.DEMO_OPERATOR}),
}


@dataclass
class ActorRegistry:
    """Server-side roster of demo actors (the only source of role/scope)."""

    actors: dict[str, Actor]

    @classmethod
    def demo(cls) -> "ActorRegistry":
        return cls({a.actor_id: a for a in (
            Actor(actor_id="DEMO-COMPANY-BAT", role=Role.COMPANY, company_id="DEMO-BAT"),
            Actor(actor_id="DEMO-COMPANY-OTHER", role=Role.COMPANY, company_id="DEMO-OTHER"),
            Actor(actor_id="DEMO-OFFICER", role=Role.OFFICER, assigned_case_ids=("CASE-BRICKS-001",)),
            Actor(actor_id="DEMO-OPERATOR", role=Role.DEMO_OPERATOR),
        )})

    def resolve(self, claimed: Actor) -> Actor:
        known = self.actors.get(claimed.actor_id)
        if known is None:
            raise BousslaError(ErrorCode.FORBIDDEN, "Acteur inconnu")
        if claimed.role != known.role or claimed.company_id != known.company_id:
            raise BousslaError(ErrorCode.FORBIDDEN, "Rôle ou entreprise non reconnus pour cet acteur")
        return known

    def assign(self, officer_id: str, case_id: str) -> None:
        officer = self.actors[officer_id]
        if officer.role is not Role.OFFICER:
            raise BousslaError(ErrorCode.FORBIDDEN, "Seul un agent peut être assigné")
        if case_id not in officer.assigned_case_ids:
            self.actors[officer_id] = officer.model_copy(
                update={"assigned_case_ids": (*officer.assigned_case_ids, case_id)})

    def unassign(self, case_id: str) -> None:
        for actor_id, actor in list(self.actors.items()):
            if case_id in actor.assigned_case_ids:
                self.actors[actor_id] = actor.model_copy(update={
                    "assigned_case_ids": tuple(c for c in actor.assigned_case_ids if c != case_id)})


def authorize(registry: ActorRegistry, claimed: Actor, action: str,
              case_company_id: str | None = None, case_id: str | None = None) -> Actor:
    """Resolve the actor and enforce role + enterprise/case scope. Returns the trusted actor."""
    actor = registry.resolve(claimed)
    allowed = POLICY.get(action)
    if allowed is None:
        raise BousslaError(ErrorCode.FORBIDDEN, f"Action inconnue : {action}")
    if actor.role not in allowed:
        raise BousslaError(ErrorCode.FORBIDDEN, "Action non autorisée pour ce rôle")
    if case_id is None:
        return actor
    if actor.role is Role.COMPANY and actor.company_id != case_company_id:
        raise BousslaError(ErrorCode.CROSS_COMPANY, "Ce dossier appartient à une autre entreprise")
    if actor.role is Role.OFFICER and case_id not in actor.assigned_case_ids:
        raise BousslaError(ErrorCode.FORBIDDEN, "Dossier non assigné à cet agent")
    return actor
