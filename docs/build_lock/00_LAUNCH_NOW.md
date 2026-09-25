# Launch now — branch prompts with mandatory atomic commits and pushes

**Update:** V4-GIT-1, 25 September 2026. Product scope remains the V4 eight-hour lock. These are instructions for your coding assistants; no team repository has been accessed, committed to or pushed by this package update.

## Distribute the complete pack once

Put all shared specifications, contracts and fixtures in the same team repository before implementation. Each person opens their own clone/worktree, reads the common documents and runs only their lane's handoff. A single handoff file without its referenced contracts/fixtures is not a self-contained project.

Fresh repository: the human captain places this folder's **contents** at repository root and establishes the initial `main`. Existing repository: place under `docs/build_lock/`, keep functioning code and existing root instructions, and set `PLAN_ROOT` accordingly. Confirm the actual team remote; no remote URL is supplied by this pack.

## Model files and branches

| Lane | Coding assistant | File to read/run | Branch |
|---|---|---|---|
| A | Claude Code / Max | [`CLAUDE_MAX_BACKEND_GRAPH.md`](handoffs/CLAUDE_MAX_BACKEND_GRAPH.md) | `feat/backend-workflow` |
| B | Codex / Pro | [`CODEX_PRO_DATA_CHECKS.md`](handoffs/CODEX_PRO_DATA_CHECKS.md) | `feat/checks-scenarios` |
| C | Codex / Plus — document lane | [`CODEX_PLUS_A_DOCUMENTS_RAG.md`](handoffs/CODEX_PLUS_A_DOCUMENTS_RAG.md) | `feat/documents-rag` |
| D | Codex / Plus — UI lane | [`CODEX_PLUS_B_UI_RELEASE.md`](handoffs/CODEX_PLUS_B_UI_RELEASE.md) | `feat/company-admin-ui` |
| REVIEW | Gemini / Pro — independent reviewer | [`GEMINI_PRO_REVIEW_TESTS.md`](handoffs/GEMINI_PRO_REVIEW_TESTS.md) | `test/independent-review` |

All assistants read the actual repository `AGENTS.md`, the pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, and `GIT_WORKFLOW.md`. Each handoff then includes its original task requirements plus the new branch/commit/push policy.

## First integration, not four sequential handovers

A publishes the small shared-contract/mock foundation as the first pushed increment, targeting the first 30 minutes. A human review merges this foundation into `main`. B uses structured fixtures, C uses sample documents, and D uses A's mock service in parallel. They do not wait for a trained model or live provider to begin.

Synchronize small reviewed increments every 45–60 minutes; target the first real upload → checks → officer case by hour 2. This does not restart the time remaining.

## Paste into each assistant after opening its repository

```text
Read your assigned updated handoff in full, along with its required shared files.
Inspect the existing repository and preserve functioning code.
Use only the exact branch and owned files in that handoff.
After EVERY coherent valid modification: run the relevant checks, inspect the
staged diff, create one atomic commit and immediately push to your assigned
branch on the confirmed team remote. Do not wait for the end of the workstream.
Never force-push or push directly to main. Do not merge without human approval.
Report the commit SHA, actual test results, push confirmation and blockers.
Start with your handoff's first small milestone now.
```

**Gemini note:** its branch is only for independent tests/reports, not production modules. If the session cannot execute Git, a human applies and tests the proposed patch and publishes it; the assistant must not claim it pushed.

## What is unchanged

`01_FINAL_LOCK.md`, the shared contract specification, architecture, scoring/data specifications, all source examples and all synthetic fixtures/reference code are retained from the supplied V4 pack. This update changes collaboration instructions, not the business rules, tool choices, legal status or benchmark claims.

See `BRANCH_PACK_VALIDATION.md` for what was actually checked during this update. The earlier `PACK_VALIDATION.md` is preserved with a note distinguishing its original checks from this documentation-only revision.
