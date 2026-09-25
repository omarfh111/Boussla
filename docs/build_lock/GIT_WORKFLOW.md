# Git workflow — V4-GIT-1

## What changed

This is an explicit collaboration update requested by the team: each assistant works on a named branch and **commits and pushes after every coherent validated change**. It does not expand V4's product scope, restart the eight-hour clock or validate an unimplemented application.

The four feature owners remain A (backend/graph), B (checks/data), C (documents/retrieval) and D (UI/release). Gemini receives only an independent test/report branch. This is not a fifth production-code lane.

## One repository, five isolated branches

| Lane | Assistant | Branch | Write ownership |
|---|---|---|---|
| A | Claude Code / Max | `feat/backend-workflow` | Backend, graph, security, case store, shared types/dependencies |
| B | Codex / Pro | `feat/checks-scenarios` | Checks, scenarios, scoring, synthetic data and their tests |
| C | Codex / Plus, document lane | `feat/documents-rag` | Documents, Jev/LLM adapters, Qdrant retrieval and tests |
| D | Codex / Plus, UI lane | `feat/company-admin-ui` | `app.py`, UI, UI tests and release packaging |
| Review | Gemini / Pro | `test/independent-review` | `reviews/gemini/`, `tests/review/`, `fixtures/review/` only |

Use one clone per teammate; if several agents run on the same machine, use separate worktrees/clones. Never run two writers in the same working directory. Each worktree has its own ignored runtime directory/environment; do not point concurrently running demos at one mutable SQLite file or Qdrant local directory.

## One-time human bootstrap

The human captain provides the correct repository, authenticated access and remote. For a new repository, import the complete pack's contents into the project root and make the source/provenance bootstrap commit before starting branches. For an existing repository, preserve all working code and existing instructions; place the pack under `docs/build_lock/` and agree that `PLAN_ROOT` points there. Do not automatically overwrite root `AGENTS.md`, dependency locks or app files.

Only the new empty project's human-reviewed initialization may establish its initial `main`. The assistants' continuing feature work never pushes directly to `main`.

A then creates the code contracts and service mock on `feat/backend-workflow`. Push this small foundation, obtain another human's review and integrate it into `main` promptly. Everyone starts from, or merges, that same foundation. B/C/D can read specifications, inspect inputs and prepare scoped tests while this happens; they must not invent permanent parallel schemas.

If a scaffold already exists, inspect and reuse it. Do not recreate branches or discard hours of functioning code because a document gives an earlier target time.

## Authorization boundary

The user's request authorizes normal atomic commits and routine pushes of source-safe work to each assigned branch on the confirmed team remote. No approval is needed after every such commit. It does not authorize arbitrary external remotes, repository creation/visibility changes, bypassing permissions, unreviewed main merges, live government access, application deployment or publication of secrets/real taxpayer records.

When Git access is missing, ask for the human's normal repository setup; never request tokens in chat or improvise credentials. Verify pushes instead of claiming success from a local commit.

## Atomic commit definition

One commit should describe one behavior, fix, contract increment, test set or documentation update. Include its required tests and directly related documentation. A mock that satisfies a declared contract is a valid scaffold when unmistakably labelled; a mock hidden behind a LIVE badge is not.

Do not split code from essential tests solely to increase commit count. Do not combine unrelated modules into a giant final commit. Do not make an empty commit or commit every keystroke. Validate that the committed snapshot is coherent without relying on untracked helper files.

Use explicit file/hunk staging, inspect `git diff --cached`, run relevant tests, create the commit and push immediately. The per-model files contain the exact branch refspec. Record test scope, actual outcomes and the new SHA.

## Merge and synchronization policy

Small PRs every 45–60 minutes are a target, not a reason to stop coding after each commit. A human A coordinates merges and another person reviews A's own changes. D verifies the integrated UI path. Each assistant reports blockers and consumer-facing interface changes before integration.

For these continuing lane branches, prefer normal merge commits for approved PRs rather than squash/rebase merging, so frequent branch synchronization does not require history rewriting. Respect an existing repository policy; the human captain decides a safe adjustment if it mandates another strategy.

At a clean checkpoint on your own branch:

```bash
git fetch origin
git merge --no-edit origin/main
# Inspect the merge and run the relevant tests and smoke check here.
# Push only after they succeed, using your assigned branch's exact refspec.
```

If a conflict touches shared contracts or another owner's files, ask that owner; do not auto-select all of ours/theirs. After a merge, tests are not optional. Incoming changes from reviewed `main` are normal synchronization, not permission to edit those owners' modules.

A same-branch non-fast-forward push must be investigated. No force/force-with-lease, reset, published rebase/amend, branch deletion or automatic stash. Preserve uncommitted work and let the owner resolve unknown divergence.

## Review branch exception

Gemini may publish independent tests/reports under its narrow owned directories. Correctly reproduced existing failures may be committed on that branch with actual evidence and `RED_UNRESOLVED — NOT READY TO MERGE`. They do not become passing tests, and they must not be merged into `main` as an allegedly green change. Missing execution environments are `NOT_EXECUTED`.

A chat-only Gemini session returns patches/reports to a human who can run and publish them; it does not pretend it has shell/Git capabilities.

## Safety and ignored material

Keep `.env`/secret files, credentials in URLs, uploads, mutable SQLite/WAL/checkpoint files, Qdrant runtime storage, raw tracing payloads, local environments/caches and real personal/taxpayer data out of commits. `.env.example` may contain names and placeholders only. Existing synthetic fixtures and permitted public-source references are not real confidential data.

A owns shared ignore/dependency changes. Every author still inspects what is actually staged; an ignore file is not a substitute for review. If credentials have already been exposed, notify the owner and arrange revocation/rotation; never silently rewrite published history.

## Ready-to-integrate versus pushed

A pushed commit is a remotely saved increment, not evidence the complete product is integrated. PR readiness requires matching shared contracts, appropriate tests, no undisclosed mock/live substitution, no secret leakage and a smoke check for the available slice. No one claims full integration or provider validation from the reference tests alone.

## Deadline

The existing hour-5 feature freeze and official deadline remain unchanged. After feature freeze: small tested fixes, review and packaging only. No new framework or model experiment. At the official freeze, follow organizer instructions; do not continue changing submitted code without authorization.
