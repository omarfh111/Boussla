"""Isolated real-service setup. This module never reads evaluation_only."""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from boussla.config import get_settings
from boussla.contracts import Actor, BousslaError, Enterprise, Role
from boussla.security import ActorRegistry
from boussla.services import BousslaAppService, _discover_document_adapters
from boussla.store import CaseStore
from boussla.retrieval.corpus import _cached_retriever, load_public_references
from boussla.retrieval.grounded_rag import ReferenceAssistant
from boussla.retrieval.lexical import LexicalReferenceRetriever
from scripts.live_judge.pack import PACK

ENV_NAMES = ("OPENAI_API_KEY", "OPENAI_CHAT_MODEL", "OPENAI_EXTRACT_MODEL", "LLM_PROVIDER",
             "TYPESAFE_API_KEY", "JEV_ENABLED", "JEV_MODEL", "QDRANT_URL", "QDRANT_API_KEY",
             "QDRANT_COLLECTION", "LANGSMITH_API_KEY", "LANGSMITH_TRACING", "LANGSMITH_PROJECT",
             "LANGSMITH_HIDE_INPUTS", "LANGSMITH_HIDE_OUTPUTS", "CASE_DB_PATH", "CHECKPOINT_DB_PATH",
             "UPLOAD_DIR", "EVENT_LOG_PATH", "GENERAL_MODEL_TIMEOUT_SECONDS")


@contextmanager
def environment(runtime: Path, mode: str, providers: set[str], private: dict):
    previous = {key: os.environ.get(key) for key in ENV_NAMES}
    try:
        for key in ENV_NAMES:
            if key in private and private[key] is not None:
                os.environ[key] = private[key]
        for provider, keys in {"openai": ("OPENAI_API_KEY",), "jev": ("TYPESAFE_API_KEY",),
                               "qdrant": ("QDRANT_URL", "QDRANT_API_KEY"),
                               "langsmith": ("LANGSMITH_API_KEY",)}.items():
            if mode != "live" or provider not in providers:
                for key in keys:
                    os.environ[key] = ""
        os.environ["LLM_PROVIDER"] = "openai" if os.environ.get("OPENAI_API_KEY") else "manual"
        os.environ["JEV_ENABLED"] = str(bool(os.environ.get("TYPESAFE_API_KEY"))).lower()
        os.environ["LANGSMITH_TRACING"] = str(bool(os.environ.get("LANGSMITH_API_KEY"))).lower()
        os.environ["LANGSMITH_PROJECT"] = "boussla-live-judge-synthetic"
        os.environ["LANGSMITH_HIDE_INPUTS"] = "true"
        os.environ["LANGSMITH_HIDE_OUTPUTS"] = "true"
        for key, name in (("CASE_DB_PATH", "cases.sqlite"), ("CHECKPOINT_DB_PATH", "checkpoints.sqlite"),
                          ("UPLOAD_DIR", "uploads"), ("EVENT_LOG_PATH", "events.jsonl")):
            os.environ[key] = str(runtime / name)
        get_settings.cache_clear()
        _cached_retriever.cache_clear()
        yield get_settings()
    finally:
        get_settings.cache_clear()
        _cached_retriever.cache_clear()
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def load_scenario(sid: str) -> dict:
    return json.loads((PACK / "scenarios" / f"{sid}.json").read_text(encoding="utf-8"))


class Case:
    def __init__(self, scenario: dict, settings, *, reference_assistant=None):
        self.scenario, self.case_id = scenario, scenario["case_id"]
        self.settings = settings
        self.store = CaseStore(settings.case_db_path, settings.upload_dir)
        self.registry = ActorRegistry({actor.actor_id: actor for actor in (
            Actor(actor_id="SYN-JUDGE-COMPANY", role=Role.COMPANY, company_id=scenario["company_id"]),
            Actor(actor_id="SYN-JUDGE-OFFICER", role=Role.OFFICER, assigned_case_ids=(self.case_id,)),
            Actor(actor_id="SYN-JUDGE-OTHER", role=Role.COMPANY, company_id="SYN-OTHER-COMPANY"),
            Actor(actor_id="SYN-JUDGE-UNASSIGNED", role=Role.OFFICER),
        )})
        self.co = self.registry.actors["SYN-JUDGE-COMPANY"]
        self.off = self.registry.actors["SYN-JUDGE-OFFICER"]
        if not self.store.case_exists(self.case_id):
            facts = json.loads((PACK / scenario["observed_file"]).read_text(encoding="utf-8"))
            from boussla.seed import fact_id, KINDS
            from boussla.contracts import PaymentAllocation, Project, Document
            models = {kind: values[1] for kind, values in KINDS.items()}
            models.update(payment_allocation=PaymentAllocation, project=Project, document=Document)
            with self.store.write(self.case_id) as tx:
                tx.create_case(scenario["company_id"], "Isolated synthetic judge fixture")
                for kind, rows in facts.items():
                    for row in rows:
                        model = models[kind].model_validate(row)
                        tx.put(kind, fact_id(kind, model), model)
                tx.commit_version("Synthetic fixture initialization")
        self.service = BousslaAppService(
            self.store, self.registry, settings=settings,
            reference_assistant=reference_assistant or ReferenceAssistant(
                LexicalReferenceRetriever(load_public_references())),
            **_discover_document_adapters(settings))
        self.service.enterprises[scenario["company_id"]] = Enterprise(
            company_id=scenario["company_id"], synthetic_mf="SYN-JUDGE-MF",
            display_name="SYNTHETIC JUDGE COMPANY", sector="SYNTHETIC",
            created_on="2025-01-01")

    @property
    def version(self):
        return self.store.case_meta(self.case_id)["version"]

    def state(self) -> dict:
        ev = self.service.evaluate(self.case_id)
        return {"version": self.version, "review_index": ev.score.review_index,
                "evidence_coverage": ev.score.evidence_coverage,
                "findings": [{"family": f.family.value, "status": f.status.value,
                              "reason": f.reason_code, "severity": f.severity,
                              "quantity_difference": f.quantity_difference,
                              "difference_millimes": f.observed_difference_millimes}
                             for f in ev.findings],
                "revision_count": len(self.store.revisions(self.case_id)),
                "accepted_evidence": [list(r.accepted_evidence_ids) for r in self.store.revisions(self.case_id)]}

    def upload(self, filename: str, key="upload"):
        return self.service.upload_document(self.co, self.case_id, (PACK / "documents" / filename).read_bytes(),
                                            filename, "application/pdf", self.version, key)

    def proposal(self, *, with_document=True, splits=None, extra=None):
        draft = self.service.prepare_clarification(self.off, self.case_id, self.version)
        request = self.service.publish_clarification(self.off, self.case_id, draft.draft_id, self.version, "publish")
        document_ids = []
        if with_document:
            document_ids = [self.upload("allocation-response.pdf").document.document_id]
        facts = self.service._facts(self.case_id)
        invoice = next(o for o in facts["invoice_observation"] if o.perspective.value == "BUYER_RECEIVED")
        payload = {"document_ids": document_ids, "allocation": {
            "transaction_id": invoice.transaction_id, "line_id": invoice.lines[0].line_id,
            "splits": splits or {"P1": "1000", "P2": "1000"}}}
        if extra:
            payload["allocation"].update(extra)
        response = self.service.submit_response(self.co, self.case_id, request.request.request_id,
                                                payload, self.version, "response")
        return response.proposal_ids[0]


def attempt(fn) -> dict:
    start = time.perf_counter()
    try:
        result = fn()
        return {"accepted": True, "value": result, "latency_ms": round((time.perf_counter()-start)*1000, 2)}
    except Exception as exc:
        # Never include exception messages (a provider may echo a credential).
        return {"accepted": False, "error_type": type(exc).__name__,
                "code": exc.code.value if isinstance(exc, BousslaError) else None,
                "latency_ms": round((time.perf_counter()-start)*1000, 2)}
