"""Adversarial test drivers. Assertions never enter application/provider inputs."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from boussla.contracts import Actor, Audience, BousslaError, FindingFamily, Mode, Role
from boussla.retrieval.corpus import load_public_references
from boussla.retrieval.grounded_rag import OpenAIReferenceNoteGenerator, ReferenceAssistant
from boussla.retrieval.lexical import LexicalReferenceRetriever
from scripts.live_judge.pack import DOCUMENTS, PACK
from scripts.live_judge.support import Case, attempt


class Checks:
    def __init__(self):
        self.items = []
        self.details = {}
        self.outcome = "PASS"

    def require(self, condition, name, *, severity="HIGH", owner="A", actual=None):
        self.items.append({"check": name, "passed": bool(condition), "severity": severity,
                           "owner": owner, "actual": actual})


def same_authority(left, right):
    return all(left[k] == right[k] for k in ("review_index", "evidence_coverage", "findings"))


def typed_rejection(result):
    return not result["accepted"] and result.get("code") is not None


def _safe(result):
    return {k: v for k, v in result.items() if k != "value"}


def exercise(case: Case, checks: Checks, expected: dict):
    s, co, off, cid = case.service, case.co, case.off, case.case_id
    handler, variant = case.scenario["handler"], case.scenario["variant"]
    before = case.state()
    checks.details["before"] = before
    if handler == "core":
        view = s.get_case(off, cid)
        checks.require(view.score.review_index == expected["review_index"], "documented_index",
                       owner="B", actual=view.score.review_index)
        checks.require(case.version == 1, "analysis_does_not_commit")
        if variant in {"partial", "reversed", "unknown_payment", "mapping"}:
            checks.require(next(f for f in view.findings if f.family is FindingFamily.SETTLEMENT).status.value
                           == "INSUFFICIENT", "unsupported_settlement_abstains", owner="B")
        checks.details["retrieval_mode"] = view.mode_by_node.get("retrieval", Mode.NOT_RUN).value
    elif handler in {"acceptance", "declaration", "history"}:
        proposal = case.proposal(with_document=handler != "declaration")
        proposed = case.state()
        checks.require(proposed["review_index"] == before["review_index"], "proposal_is_non_authoritative")
        old_revisions = [r.model_dump(mode="json") for r in case.store.revisions(cid)]
        result = attempt(lambda: s.accept_evidence(off, cid, proposal, case.version, "accept"))
        checks.details["acceptance"] = _safe(result)
        if handler == "declaration":
            checks.require(typed_rejection(result), "documentless_acceptance_rejected", severity="CRITICAL",
                           actual=_safe(result))
            checks.require(same_authority(proposed, case.state()), "unsupported_claim_cannot_clear_index",
                           severity="CRITICAL", actual=case.state()["review_index"])
        else:
            checks.require(result["accepted"] and case.state()["review_index"] == 0, "accepted_evidence_40_to_0")
            checks.require(case.version == proposed["version"] + 1, "one_acceptance_revision")
            checks.require([r.model_dump(mode="json") for r in case.store.revisions(cid)[:-1]] == old_revisions,
                           "old_revisions_immutable")
    elif handler == "document":
        result = attempt(lambda: case.upload(variant))
        checks.details["upload"] = _safe(result)
        if variant in {"corrupted.pdf", "oversized.pdf"}:
            checks.require(typed_rejection(result), "invalid_document_typed_rejection", owner="C", actual=_safe(result))
            checks.outcome = "SAFE_REJECTION"
        elif result["accepted"]:
            doc = result["value"]
            checks.details["routing"] = doc.routing.model_dump(mode="json") if doc.routing else None
            checks.details["extraction_mode"] = doc.extraction.mode.value if doc.extraction else "NOT_RUN"
            checks.require(doc.extraction is None or doc.extraction.status == "PROPOSED", "extraction_not_accepted")
            if not doc.extraction or doc.extraction.mode is Mode.MANUAL or doc.extraction.missing_fields:
                checks.outcome = "MANUAL_REQUIRED"
        else:
            checks.require(typed_rejection(result), "safe_document_error", owner="C", actual=_safe(result))
            checks.outcome = "SAFE_REJECTION"
        checks.require(same_authority(before, case.state()), "document_cannot_mutate_score", severity="CRITICAL")
    elif handler == "stale":
        s.submit_context(co, cid, {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": "Synthétique"}, 1, "ctx")
        result = attempt(lambda: s.submit_context(co, cid, {"purpose_text": "stale"}, 1, "stale"))
        checks.require(result.get("code") == "STALE_REVISION", "stale_version_rejected", actual=_safe(result))
        checks.require(case.version == 2, "stale_write_no_revision")
        checks.outcome = "SAFE_REJECTION"
    elif handler in {"double", "concurrent"}:
        if handler == "double":
            draft = s.prepare_clarification(off, cid, case.version)
            version = case.version
            request = s.publish_clarification(off, cid, draft.draft_id, version, "p")
            replay = s.publish_clarification(off, cid, draft.draft_id, version, "p")
            checks.require(request == replay and case.version == version + 1, "publish_exact_retry")
            different = attempt(lambda: s.publish_clarification(off, cid, draft.draft_id, case.version, "p2"))
            checks.require(typed_rejection(different), "publish_new_key_cannot_duplicate")
            doc = case.upload("allocation-response.pdf")
            invoice = s._facts(cid)["invoice_observation"][0]
            payload = {"document_ids": [doc.document.document_id], "allocation": {
                "transaction_id": invoice.transaction_id, "line_id": invoice.lines[0].line_id,
                "splits": {"P1": "1000", "P2": "1000"}}}
            version = case.version
            response = s.submit_response(co, cid, request.request.request_id, payload, version, "r")
            replay = s.submit_response(co, cid, request.request.request_id, payload, version, "r")
            checks.require(response == replay and case.version == version + 1, "response_exact_retry")
            conflict = attempt(lambda: s.submit_response(co, cid, request.request.request_id,
                {**payload, "answers": {"Q-PROJECT-ALLOCATION": "different"}}, version, "r"))
            checks.require(conflict.get("code") == "IDEMPOTENCY_CONFLICT", "response_conflicting_key")
            proposal = response.proposal_ids[0]
        else:
            proposal = case.proposal()
        version = case.version
        if handler == "concurrent":
            # Two real SQLite-backed service clients race the same expected version.
            second = Case(case.scenario, case.settings)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(attempt, lambda service=service, key=key:
                    service.accept_evidence(off, cid, proposal, version, key))
                           for service, key in ((s, "a"), (second.service, "b"))]
                results = [f.result() for f in futures]
            checks.require(sum(r["accepted"] for r in results) == 1, "two_clients_one_winner", actual=[_safe(r) for r in results])
            checks.require(any(r.get("code") == "STALE_REVISION" for r in results), "two_clients_stale_loser")
        else:
            first = s.accept_evidence(off, cid, proposal, version, "a")
            replay = s.accept_evidence(off, cid, proposal, version, "a")
            checks.require(replay.replayed and replay.new_version == first.new_version, "accept_exact_retry")
            rejected = attempt(lambda: s.accept_evidence(off, cid, proposal, case.version, "a2"))
            checks.require(rejected.get("code") == "DUPLICATE_ACCEPTANCE", "accept_new_key_cannot_duplicate")
        checks.require(case.version == version + 1, "one_canonical_acceptance")
    elif handler == "roles":
        attempts = [
            lambda: s.list_queue(co, None, 5),
            lambda: s.get_case(case.registry.actors["SYN-JUDGE-OTHER"], cid),
            lambda: s.get_case(case.registry.actors["SYN-JUDGE-UNASSIGNED"], cid),
            lambda: s.get_case(Actor(actor_id=co.actor_id, role=Role.OFFICER), cid),
            lambda: s.get_case(Actor(actor_id="SYN-UNKNOWN", role=Role.OFFICER), cid),
            lambda: s.create_case(co, "SYN-OTHER-COMPANY", {"label": "attack"}, "attack"),
        ]
        results = [attempt(action) for action in attempts]
        checks.require(all(typed_rejection(r) for r in results), "role_scope_enforced", severity="CRITICAL",
                       actual=[_safe(r) for r in results])
        data = s.get_case(co, cid).model_dump(mode="json")
        checks.require(not {"findings", "score", "reference_note", "candidate_passages"} & data.keys(),
                       "company_internal_fields_absent", severity="CRITICAL")
        checks.outcome = "SAFE_REJECTION"
    elif handler == "tamper":
        checks.details["tamper_cases"] = []
        variants = {"negative": {"splits": {"P1": "-1", "P2": "2001"}},
                    "nan": {"splits": {"P1": "NaN"}}, "infinity": {"splits": {"P1": "Infinity"}},
                    "huge_decimal": {"splits": {"P1": "1e999999999"}},
                    "overflow": {"splits": {"P1": "2000", "P2": "1000"}},
                    "unknown_project": {"splits": {"NO-PROJECT": "2000"}},
                    "unknown_transaction": {"extra": {"transaction_id": "NO-TX"}},
                    "wrong_unit": {"extra": {"unit": "tonne"}},
                    "wrong_currency": {"extra": {"currency": "EUR"}}}
        for name, options in variants.items():
            settings = replace(case.settings, case_db_path=case.settings.case_db_path.parent / name / "case.sqlite",
                               upload_dir=case.settings.upload_dir.parent / name / "uploads")
            child = Case(case.scenario, settings)
            def act():
                pid = child.proposal(**options)
                return child.service.accept_evidence(child.off, cid, pid, child.version, "accept")
            result = attempt(act)
            checks.details["tamper_cases"].append({"input": options, "variant": name,
                "before": before, "after": child.state(), "result": _safe(result)})
            checks.require(typed_rejection(result), f"tamper_{name}_typed_rejection", severity="MEDIUM",
                           actual=_safe(result))
            checks.require(child.state()["review_index"] == before["review_index"], f"tamper_{name}_no_score_change",
                           severity="HIGH", actual=child.state()["review_index"])
        for cursor in ("abc", "-1", "1.5", "NaN"):
            result = attempt(lambda: s.list_queue(off, None, 10, cursor))
            checks.require(typed_rejection(result), "bad_cursor_" + cursor, severity="MEDIUM", actual=_safe(result))
        checks.outcome = "SAFE_REJECTION"
    elif handler in {"purpose", "extra_fields"}:
        values = ["", "🏗️", "texte " * 10000, "chantier bcp de stock", "travaux project", "مشروع travaux"]
        for n, value in enumerate(values if handler == "purpose" else ["synthetic"]):
            payload = {"purpose_category": "CONSTRUCTION_PROJECT", "purpose_text": value}
            if handler == "extra_fields":
                payload.update(review_index=0, arbitrary_property="not-in-contract")
            result = attempt(lambda: s.submit_context(co, cid, payload, case.version, f"ctx-{n}"))
            if handler == "extra_fields":
                checks.require(typed_rejection(result), "unexpected_properties_rejected", severity="MEDIUM", actual=_safe(result))
            else:
                checks.require(result["accepted"] or typed_rejection(result), f"purpose_{n}_safe", severity="MEDIUM")
            checks.require(same_authority(before, case.state()), f"purpose_{n}_non_authoritative", severity="CRITICAL")
        for dates in (("not-a-date", "2026-10-01"), ("2026-10-01", "2026-01-01")):
            result = attempt(lambda: s.submit_context(co, cid, {"planned_start": dates[0], "planned_end": dates[1]},
                                                      case.version, str(dates)))
            checks.require(typed_rejection(result), "invalid_dates_typed_rejection", severity="MEDIUM", actual=_safe(result))
    elif handler in {"documents", "duplicates"}:
        results = []
        names = DOCUMENTS if handler == "documents" else ["invoice-fr.pdf", "duplicate.pdf", "near-duplicate.pdf"]
        for n, filename in enumerate(names):
            result = attempt(lambda: case.upload(filename, f"doc-{n}"))
            results.append({"file": filename, **_safe(result)})
            checks.require(result["accepted"] or typed_rejection(result), "document_safe_" + filename,
                           owner="C", severity="MEDIUM", actual=_safe(result))
            checks.require(same_authority(before, case.state()), "document_authority_" + filename, severity="CRITICAL")
            if filename in {"six-pages.pdf", "oversized.pdf"}:
                checks.require(result.get("code") == "LIMIT_EXCEEDED", "document_limit_" + filename, owner="A")
            if filename == "duplicate.pdf":
                checks.require(not result["accepted"], "duplicate_not_independent")
        checks.details["documents"] = results
        content = (PACK / "documents" / "payment.pdf").read_bytes()
        result = attempt(lambda: s.upload_document(co, cid, content, "../../escape.pdf", "application/pdf", case.version, "path"))
        if result["accepted"]:
            doc = result["value"].document
            checks.require(Path(doc.local_path).resolve().is_relative_to(case.settings.upload_dir.resolve()),
                           "upload_path_contained", severity="CRITICAL")
            checks.require(doc.original_filename == "escape.pdf", "filename_sanitized", severity="MEDIUM")
    elif handler.startswith("restart"):
        arg = ""
        if handler == "restart_decision":
            arg = case.proposal()
        steps = ["analysis-start", "analysis-resume", "analysis-resume"] if handler == "restart_analysis" else [
            "decision-start", "decision-resume", "decision-resume"]
        results = []
        start_version = case.version
        for step in steps:
            child = subprocess.run([sys.executable, "-m", "scripts.live_judge.worker", case.scenario["scenario_id"],
                                    str(case.settings.case_db_path.parent), step, arg], capture_output=True, text=True,
                                   encoding="utf-8", timeout=90)
            try:
                result = json.loads(child.stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                result = {"error_type": "WorkerFailed", "returncode": child.returncode}
            results.append(result)
        checks.details["process_restarts"] = results
        checks.require(case.version == start_version + 1, "restart_exactly_one_mutation", actual=case.version)
        checks.require(results[0].get("interrupted") is True, "restart_reached_interrupt")
        if handler == "restart_decision":
            checks.require(case.state()["review_index"] == 0, "restart_decision_40_to_0")
    else:
        from scripts.live_judge.provider_checks import offline_provider_checks
        offline_provider_checks(case, checks)
        checks.require(same_authority(before, case.state()), "assistive_failure_cannot_change_authority", severity="CRITICAL")
    checks.details["after"] = case.state()
