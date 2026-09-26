"""Run isolated offline/live judge scenarios and write sanitized reports.

Example: python -m scripts.live_judge.run --mode offline --all
Live: --mode live --scenario JUDGE-047,JUDGE-048 --env-file ../.env --update
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

from scripts.live_judge.checks import Checks, exercise, same_authority
from scripts.live_judge.pack import PACK, ROOT
from scripts.live_judge.support import Case, ENV_NAMES, environment, load_scenario

OUTCOMES = ("PASS", "SAFE_REJECTION", "SAFE_FALLBACK", "MANUAL_REQUIRED", "BUG", "NOT_RUN")
BASE_SHA = "320e36bdc1733e0e7097fff37406cd7ec040a4ee"


def sha():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def ab_check(scenario, checks, runtime, private, providers, cache):
    from boussla.workflow import WorkflowRunner
    from boussla.retrieval.grounded_rag import ReferenceAssistant, OpenAIReferenceNoteGenerator
    from scripts.live_judge.provider_checks import cloud_retriever
    if not all(private.get(key) or os.getenv(key) for key in
               ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "QDRANT_URL", "QDRANT_API_KEY")):
        checks.outcome = "NOT_RUN"
        checks.details["reason"] = "FULL_LIVE_AB_PROVIDER_CONFIGURATION_MISSING"
        return
    rows = []
    for sid in ("JUDGE-001", "JUDGE-002", "JUDGE-006"):
        observations = {}
        for mode in ("offline", "live"):
            workflow_start = time.perf_counter()
            folder = runtime / sid / mode
            with environment(folder, mode, providers, private) as settings:
                assistant = None
                if mode == "live":
                    audit = []
                    retriever = cloud_retriever(cache, audit)
                    assistant = ReferenceAssistant(retriever, OpenAIReferenceNoteGenerator(
                        api_key=settings.secret("OPENAI_API_KEY"), model=settings.openai_chat_model))
                case = Case(load_scenario(sid), settings, reference_assistant=assistant)
                before = case.state()
                view = case.service.get_case(case.off, case.case_id)
                runner = WorkflowRunner(case.service, planner=None if mode == "offline" else
                                        __import__("boussla.workflow", fromlist=["openai_planner"]).openai_planner)
                analysis = runner.run_analysis(case.co, case.case_id, case.version)
                runner.close()
                doc = case.upload("prompt-injection.pdf", "injection")
                checks.require(same_authority(before, case.state()), f"{sid}_{mode}_ai_non_authoritative", severity="CRITICAL")
                if sid == "JUDGE-006":
                    proposal = case.proposal()
                    case.service.accept_evidence(case.off, case.case_id, proposal, case.version, "accepted")
                state = case.state()
                state["accepted_evidence"] = [len(ids) for ids in state["accepted_evidence"]]
                observations[mode] = state
                rows.append({"scenario": sid, "mode": mode, "priority_before": before["review_index"],
                             "priority_after": state["review_index"],
                             "planner_mode": analysis.mode_by_node["planner"].value,
                             "full_workflow_latency_ms": round((time.perf_counter()-workflow_start)*1000, 2),
                             "extraction_mode": doc.extraction.mode.value if doc.extraction else "NOT_RUN",
                             "routing_mode": doc.routing.mode.value if doc.routing else "NOT_RUN",
                             "retrieval_mode": view.mode_by_node.get("retrieval").value,
                             "reference_note_present": view.reference_note is not None})
        checks.require(observations["live"] == observations["offline"], f"{sid}_live_fallback_authority_equal",
                       severity="CRITICAL", actual={"live": observations["live"], "fallback": observations["offline"]})
    checks.details["ab_results"] = rows


def run_one(sid, *, mode="offline", providers=None, private=None, cache=None):
    providers, private = providers or set(), private or {}
    scenario = load_scenario(sid)
    checks = Checks()
    start = time.perf_counter()
    handler = scenario["handler"]
    # Runtime-facing loader above does not access this oracle. It is read only by the evaluator.
    expected = json.loads((PACK / "evaluation_only" / "outcomes.json").read_text(encoding="utf-8"))[sid]
    if handler.startswith("pending"):
        checks.outcome = "NOT_RUN"
        checks.details.update(status="PENDING", reason="AWAITING_CONTEXT_INTEGRATION" if handler == "pending_context"
                              else "AWAITING_REACT_HTTP_INTEGRATION", prepared_input=scenario.get("context_input"))
    elif mode != "live" and handler in {"live", "ab"}:
        checks.outcome = "NOT_RUN"
        checks.details["reason"] = "LIVE_MODE_REQUIRED"
    else:
        # OS temporary directory; never the developer's normal runtime/ database.
        with tempfile.TemporaryDirectory(prefix="boussla-judge-") as directory:
            runtime = Path(directory)
            try:
                if handler == "ab":
                    ab_check(scenario, checks, runtime, private, providers, cache)
                else:
                    with environment(runtime, mode, providers, private) as settings:
                        case = Case(scenario, settings)
                        if handler == "live":
                            from scripts.live_judge.provider_checks import live_checks
                            live_checks(case, checks, cache, expected)
                        else:
                            exercise(case, checks, expected)
            except Exception as exc:
                # A runner/setup error is not automatically a product defect or a pass.
                checks.outcome = "NOT_RUN"
                checks.details["runner_error_type"] = type(exc).__name__
    failures = [item for item in checks.items if not item["passed"]]
    outcome = "BUG" if failures else checks.outcome
    return {"scenario_id": sid, "description": scenario["description"], "outcome": outcome,
            "recorded_at": datetime.now(timezone.utc).isoformat(), "production_base_sha": BASE_SHA,
            "execution_mode": mode, "latency_ms": round((time.perf_counter()-start)*1000, 2),
            "checks": checks.items, "failures": failures, "details": checks.details,
            "runtime_isolated": True, "runtime_cleaned": True}


def render(report):
    lines = ["# LIVE JUDGE GAUNTLET — ROUND 1", "", f"Tested commit: `{report['git_sha']}`",
             f"Base main: `{BASE_SHA}`", f"Recorded: {report['timestamp']}", "",
             "Synthetic only. Production code is unchanged. Fault injection is labelled offline; it is not a live-provider success.",
             "", "## Outcomes", "", "| Outcome | Count |", "|---|---:|"]
    lines += [f"| {name} | {report['counts'][name]} |" for name in OUTCOMES]
    lines += ["", "## Scenario matrix", "", "| Scenario | Situation | Mode | Outcome |", "|---|---|---|---|"]
    lines += [f"| {row['scenario_id']} | {row['description']} | {row['execution_mode']} | {row['outcome']} |"
              for row in report["scenarios"]]
    lines += ["", "## Defects", ""]
    for row in report["scenarios"]:
        for failure in row["failures"]:
            lines.append(f"- **{failure['severity']} / {failure['owner']} / {row['scenario_id']}**: {failure['check']}")
    lines += ["", "## Interpretation", "",
              "Each scenario has exactly one outcome. A scenario with any violated invariant is BUG. NOT_RUN is never a pass.",
              "See report.json for before/after states, typed errors, privacy booleans and measured provider latencies.",
              "Context and React scenarios remain PENDING until the captain authorizes Round 2 on their merged main.",
              "Live model wording can vary. This tests invariants and synthetic routing, not legal accuracy or real-world performance.",
              "Live configurations use the explicit private dotenv path; values, raw headers and provider error messages are never reported.",
              "Runtime databases use disposable per-scenario OS temporary directories. No developer demo database was touched.",
              "", "ROUND 2 REQUIRED: YES. No production fixes or main merge were performed.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--scenario", help="Comma-separated scenario IDs")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--providers", default="openai,jev,qdrant,langsmith")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "results/live_judge/report.json")
    parser.add_argument("--update", action="store_true", help="Replace selected scenario rows in the existing report")
    args = parser.parse_args()
    if not args.all and not args.scenario:
        parser.error("choose --all or --scenario")
    private = dict(dotenv_values(args.env_file)) if args.env_file else {}
    selected = args.scenario.split(",") if args.scenario else [Path(p).stem for p in
        json.loads((PACK / "manifest.json").read_text(encoding="utf-8"))["scenarios"]]
    providers = set(args.providers.split(","))
    cache = Path(tempfile.gettempdir()) / "boussla-judge-public-embedding-cache"
    rows = []
    for sid in selected:
        result = run_one(sid, mode=args.mode, providers=providers, private=private, cache=cache)
        rows.append(result)
        print(f"{sid}: {result['outcome']}", flush=True)
    if args.update and args.report.exists():
        previous = json.loads(args.report.read_text(encoding="utf-8"))
        rows += [r for r in previous["scenarios"] if r["scenario_id"] not in selected]
    rows.sort(key=lambda row: row["scenario_id"])
    counts = Counter(row["outcome"] for row in rows)
    config = {name: bool(private.get(name) or os.getenv(name)) for name in
              ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "QDRANT_URL", "QDRANT_API_KEY", "LANGSMITH_API_KEY")}
    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "git_sha": sha(), "base_main_sha": BASE_SHA,
              "branch": "test/live-judge-gauntlet", "scenario_count": len(rows),
              "provider_configuration_present": config, "providers_selected": sorted(providers),
              "counts": {name: counts[name] for name in OUTCOMES}, "scenarios": rows,
              "round_2_required": True, "production_files_changed": False}
    serialized = json.dumps(report, indent=2, ensure_ascii=False)
    # Fail closed if a configured secret unexpectedly reaches the report serializer.
    secrets = [private.get(k) or os.getenv(k) for k in config if k.endswith("API_KEY")]
    if any(secret and len(secret) > 8 and secret in serialized for secret in secrets):
        raise RuntimeError("REPORT_SECRET_SCAN_FAILED")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(serialized + "\n", encoding="utf-8")
    args.report.with_suffix(".md").write_text(render(report), encoding="utf-8")
    print(json.dumps(report["counts"]))


if __name__ == "__main__":
    main()
