> **Branch-start update V4-GIT-1:** read [00_LAUNCH_NOW.md](00_LAUNCH_NOW.md) first. Every handoff now names its branch and requires validation → atomic commit → immediate push. The product scope below is unchanged.

# BOUSSLA Context — Eight-hour build pack

**Decision:** build a two-view, evidence-based clarification workflow for company transactions. Do not build an autonomous fraud court or a national compulsory invoicing platform.

**Time budget:** eight hours from the team's actual start, or less if the organizer's deadline comes first. Freeze features at hour 5; reserve the final three hours for tests, fixes, rehearsal and submission.

**Status:** this pack contains a design, five coding/review handoffs, explicit contracts, synthetic sample documents and a small reference implementation. It is not a finished BOUSSLA application. Provider integrations, production authentication and business/legal validation are not established by this pack. See `PACK_VALIDATION.md` for exactly what was run.

## What to send each assistant

Every coding assistant reads `AGENTS.md`, `01_FINAL_LOCK.md` and `contracts/CONTRACTS.md` first. Then:

| Human workstream | Coding assistant available to the team | Main file | Ownership |
|---|---|---|---|
| A, integration captain | Claude Code with Max 5x | `handoffs/CLAUDE_MAX_BACKEND_GRAPH.md` | Service layer, SQLite, LangGraph, permissions, acceptance and revisions |
| B | Codex with Pro | `handoffs/CODEX_PRO_DATA_CHECKS.md` | Observed data, deterministic checks, scenarios, scoring and evaluation |
| C | First Codex with Plus | `handoffs/CODEX_PLUS_A_DOCUMENTS_RAG.md` | PDF interpretation, Jev, Qdrant, provenance inspection, model adapters |
| D | Second Codex with Plus | `handoffs/CODEX_PLUS_B_UI_RELEASE.md` | Streamlit company/admin views, integration UI, release and demo |
| Shared reviewer, not a fifth developer | Gemini Pro | `handoffs/GEMINI_PRO_REVIEW_TESTS.md` | Independent test cases, diff review, source/claim audit, pitch criticism |

These are role assignments, not claims about which model is inherently best. Four humans own four code lanes. Gemini reviews snapshots or diffs; it does not concurrently rewrite shared files.

**Max 5x is an account plan label, not five independent developer seats.** Account access, usage limits and provider API access must be checked by each owner. Do not share credentials or attempt to bypass subscription limits.

## Read order and time

1. Everyone: this page and `01_FINAL_LOCK.md` (about ten minutes total).
2. A publishes the contracts, skeleton service and mock return objects by minute 30.
3. B/C/D implement their own directories against those contracts; no waiting for a complete model.
4. First integrated slice by hour 2. If it fails, reduce scope immediately.

## Repository use

Inspect existing code before copying anything. Preserve functioning code; this pack is not a reason to restart an application. Copy documents into `docs/build_lock/` if helpful. The `reference/` code is a tested arithmetic/provenance scaffold, not a replacement for the real service, extractor or UI. The fixtures are explicitly synthetic and must not enter a claimed real-world fraud benchmark.

Expected implementation layout:

```text
app.py                     # D
boussla/contracts.py       # A owns shared types
boussla/services.py        # A; only public entry point for UI writes
boussla/store.py           # A
boussla/workflow.py        # A: LangGraph
boussla/security.py        # A
boussla/observability.py   # A
boussla/checks/            # B
boussla/scenarios/         # B
boussla/scoring.py         # B
boussla/data/              # B
boussla/documents/         # C
boussla/adapters/          # C: Jev and one LLM provider
boussla/retrieval/         # C: Qdrant
ui/                       # D
scripts/                  # scripts owned by their module owner
runtime/                  # ignored, databases and uploads
results/                  # measured, scoped test reports
```

Only A edits shared contracts/dependency files after the initial freeze. Other owners propose changes in `handoffs/CHANGE_REQUESTS.md`. D owns `app.py`. Never have four assistants overwrite the same file.

## Useful existing files in this pack

`docs/ARCHITECTURE.md` — bounded multi-agent graph and storage.

`docs/DATA_AND_FIXTURES.md` — precise source grains, planned volume and synthetic cases.

`docs/SCORING_AND_SCENARIOS.md` — arithmetic, no inverse loyalty, no automatic late-response punishment.

`docs/DOCUMENT_INTEGRITY.md` — what hashes, signatures, C2PA and detectors can/cannot establish.

`docs/TESTS_AND_8H_PLAN.md` — tests, hourly gates, cut rules and submission requirements.

`docs/SOURCES.md` — public references actually consulted and limitations.

`docs/DEMO_AND_PITCH.md` — five-minute narrative and 12-slide content outline.

## First command that already works in the pack

From this directory:

```bash
python -m unittest discover -s reference -p 'test_*.py' -v
```

That runs the reference checks only. The application launch commands in the handoffs are targets to implement, not claims that `app.py` is already supplied.
