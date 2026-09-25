# Claude Code / Max — Lane A: backend, graph and integration captain

**Branch-start revision: V4-GIT-1.** This update adds branch execution, atomic commits and pushes. It does not change the product's eight-hour scope or replace the original lane responsibilities reproduced below.

## Assigned branch and startup prompt

**Model/workstream:** Claude Code / Max  
**Lane:** `A`  
**Assigned branch:** `feat/backend-workflow`  
**Remote:** the existing human-confirmed team remote, normally `origin`.  
**Integration branch:** `main` unless the human captain explicitly confirms the repository uses another base.

> Start implementing/reviewing the assigned V4 workstream now. Read this entire handoff and its shared dependencies. Work only on `feat/backend-workflow` in your isolated repository checkout. After every coherent valid modification, run relevant checks, make an atomic commit and immediately push it to `origin/feat/backend-workflow`. Do not wait until the workstream is complete. Keep source-safe commits scoped; never push directly to `main` or merge a PR without explicit human approval.

### Before editing

Read the repository's actual `AGENTS.md` first, then this build pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `GIT_WORKFLOW.md` and the module-specific documents below. The V4 eight-hour lock remains the product specification; older V1/V2/V3 plans are background, not another scope to implement.

The human must provide the complete pack in the repository. `PLAN_ROOT` is the pack location: repository root for a fresh project, or normally `docs/build_lock/` in an existing project. Documentation/fixture paths in this handoff are relative to `PLAN_ROOT`; implementation paths such as `boussla/` and `ui/` are relative to repository root. Do not copy an `AGENTS.md` over existing repository instructions without review. Missing documents or conflicting actual repository instructions must be reported, not silently invented/replaced.

Inspect the repository root, current branch, working-tree status, recent commits and remote. Confirm the remote is the intended team repository; never invent a GitHub URL, change visibility or log credentials from a remote URL. If no repository/remote is configured, ask the human captain for that one-time setup. Never replace `origin` or initialize a nested repository to make these commands appear to work.

### Branch creation/resume

Only after confirming the correct isolated checkout, a safe working-tree state and the authorized remote, use the following POSIX/Git Bash sequence (adapt syntax to your actual shell). If already on this branch with known in-progress work, preserve it and skip branch switching until a clean checkpoint.

```bash
BRANCH='feat/backend-workflow'
git fetch origin
if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  git switch --track -c "$BRANCH" "origin/$BRANCH"
else
  git switch -c "$BRANCH" origin/main
fi
git branch --show-current
git status --short
```

If `origin/main` is absent or a branch is checked out in another worktree, stop and ask the captain for the proper base/worktree. Never use `git switch -C` to reset it. Check whether an existing same-name remote branch contains commits missing locally; reconcile safely at a clean checkpoint rather than overwriting them.

**First milestone:** Publish shared contracts and a labelled mock service within the first 30 minutes. Push that small, tested foundation and request an immediate foundation PR review; do not wait for the complete backend.

## Required delivery loop: validate → atomic commit → push

**For every coherent, valid modification, run the relevant validation, create one atomic Git commit and immediately push that commit to your assigned branch. Do not wait for the end of the workstream or another teammate's completion.**

An atomic change is one reviewable behavior/fix with its directly related tests and necessary documentation—not every saved line, and not an unrelated bundle of features. Small, tested, explicitly labelled scaffolds are acceptable; broken or misleading implementations are not.

1. Inspect the diff and restrict it to your owned files. Keep tests with the behavior they verify. Do not sneak in formatting of other modules, unrelated refactors or dependency updates.
2. Run targeted tests and the available agreed smoke check. For a documentation-only change, inspect its content/links and run `git diff --check`. Do not invent test filenames, counts or successful commands. Distinguish pre-existing failures, failures introduced by this change and untested external integrations.
3. Verify the committed content is the content you validated: do not rely on unstaged/untracked helper code to make the staged change pass. Inspect staged additions, removals and deletions.
4. Stage explicit paths or selected hunks. Do **not** use `git add .`, `git add -A` or `git commit -a`. Never stage another person's work, credentials, real taxpayer files, mutable databases/uploads, Qdrant runtime storage or checkpoint/log payloads. Example environment files must contain placeholders only.
5. Run `git diff --cached --check` and inspect `git diff --cached`. Confirm the change has no new regressions in the exercised scope and is internally consistent. Tests dependent on an absent upstream module can use a labelled mock; this does not establish full integration.
6. Commit with a descriptive message such as `feat(checks): reconcile partial payments`. Include the actual validation summary in the commit body or delivery report. Never bypass commit hooks or required signing, backdate commits, or misattribute authorship.
7. Immediately push to the exact assigned remote branch. The user has requested this commit/push behavior; no repeated approval is needed for each ordinary in-scope push after the repository/remote have been verified. This does not authorize pushing to `main`, arbitrary remotes, production deployment or main-branch merges.
8. Confirm push success and compare local HEAD with the exact remote branch ref. Report the commit SHA and push result. If blocked by authentication, network or branch protection, keep the local commit, report `PUSH_BLOCKED`, and ask the human to resolve access. Never claim the commit is remotely available when it is not.

If a new failing change is not ready, finish the smallest valid increment first rather than commit a broken feature as “done.” A reviewer-only, explicitly labelled red reproducer has the exception described in the Gemini handoff; it is not a main-branch-ready feature.

## Collaboration and history safety

Use an isolated clone/worktree. Do not switch branches in another running agent's working directory. Verify and preserve existing changes before checkout; do not reset, stash or delete unknown work. If this is a resumed session already on your assigned branch, inspect your own pending changes and continue them without recreating the branch.

A owns shared contracts/dependency files and D owns `app.py`. Propose cross-lane changes through the human captain or a draft PR comment; A consolidates the shared change-request record. Do not have all agents append conflicting versions of one shared coordination file.

Synchronize merged `main` changes at clean, tested checkpoints, approximately every 45–60 minutes. Merge `origin/main` into your own branch; do not rewrite already pushed history. Resolve only conflicts you understand within your ownership; escalate shared-contract conflicts. Never use blanket `ours`/`theirs` resolution.

No force push, `--force-with-lease`, `git reset --hard`, `git clean -fd`, destructive branch recreation, remote replacement, branch deletion, global author/config changes, protection bypass or automatic main merge. Do not amend or rebase a published commit; make a follow-up fix commit. If a secret is exposed, stop further publication and have the owner revoke/rotate it; do not attempt unauthorized history rewriting.

Open a small PR when a useful slice is ready, even while the rest of your lane is unfinished. Mark incomplete integration as draft. Human captain A coordinates the merge with another reviewer, and D runs the UI smoke path. Routine branch pushes are not themselves approval for integration.

## Report after each pushed increment

```text
Lane / branch:
Commit SHA:
Atomic change:
Owned files changed:
Validation commands and actual results:
Existing failures / untested integrations:
Modes: LIVE / MOCK / MANUAL / TEMPLATE / NOT_RUN:
Push: confirmed / PUSH_BLOCKED (sanitized reason):
Shared-contract or dependency request:
Smallest next integration step:
```

Continue within the owned scope after a successful increment; do not stop merely because one commit was pushed. Pause for a real blocker, ownership conflict or human review requirement. At the existing hour-5 feature freeze, only tests, fixes and packaging continue. The deadline has not restarted.

## Commit/push command pattern for this lane

The paths and test name below are **examples to use only after those files/tests actually exist**. Adapt them to the real owned change; do not claim these commands have already been executed. Inspect the diff and use the exact relevant tests before staging. Run commands step by step; a failed check stops the commit/push sequence.

```bash
# Validate the one logical change first.
python -m pytest -q tests/backend/test_service_contract.py
git diff --check

# Stage only files for that validated change.
git add -- boussla/contracts.py boussla/services.py tests/backend/test_service_contract.py
git diff --cached --check
git diff --cached --stat
git diff --cached

# Commit only after the inspection and checks succeed.
git commit -m "chore(contracts): publish typed case views and mock service"

# Publish only this branch; repeat after EACH valid atomic commit.
git push -u origin HEAD:refs/heads/feat/backend-workflow

# Compare these SHAs before claiming the remote is up to date.
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/feat/backend-workflow
```

Push rejection is not permission to force push. Fetch and inspect remote divergence with the owner. Synchronization commits must also be tested before push. Keep actual secrets, mutable runtime files and confidential material out of the entire outgoing diff/history, not merely out of the latest file view.

### Integration-captain boundary

You coordinate interfaces; you do not take over B/C/D's implementation. A human captain and another reviewer approve integration into `main`. This handoff authorizes your branch commits/pushes, not autonomous main merges, bypassing branch protection, or editing repository settings.

Publish the foundation commit SHA and the mock import path to B/C/D. Prefer a reviewed normal merge of the small foundation into `main`, then let everyone merge `origin/main` into their own branch. The team must not maintain different definitions of shared types.

Own shared dependency/lock files and package initialization. Do not install new frameworks or rewrite a functioning stack. Record proposed shared changes from B/C/D; decide the smallest compatible update and notify all consumers before merging it.

## Suggested small commit milestones

These are examples, not permission to create empty commits or pretend a feature exists. Keep each actual commit internally coherent with its tests; split or combine only where needed for correctness.

| Example subject | Evidence before publication |
|---|---|
| `chore(contracts): publish V4 case views and service mock` | Shared Pydantic types, adapter interfaces and typed fake views; import/shape tests pass; no live model dependency. |
| `feat(store): persist immutable case revisions` | SQLite storage, scope checks and a tested single-case read path. |
| `feat(workflow): connect document and financial adapters` | Connect B/C behind the published interfaces; missing adapters use clearly labelled test doubles. |
| `feat(review): apply evidence with idempotent revision guards` | Wrong-company, stale-version, duplicate and identical-retry tests pass. |
| `feat(observability): trace workflow with redacted payloads` | Tracing failure does not block actions; raw documents and credentials are excluded. |

## Original V4 implementation handoff — preserved below

Read `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `docs/ARCHITECTURE.md` and `docs/TESTS_AND_8H_PLAN.md`. Inspect the existing repository before editing. You own A's files, not everyone else's implementation.

## Goal

Deliver the shared service boundary that makes company submission -> analysis -> officer clarification -> company response -> accepted revision reliable. Use a modular Python/Streamlit application, not a new microservice platform. LangGraph orchestrates, SQLite commits facts, LangSmith observes redacted node behavior.

## Own

`boussla/contracts.py`, `services.py`, `store.py`, `workflow.py`, `security.py`, `observability.py`, schema migrations and dependency locks. All other files remain with their named owner unless they request help.

## First 30 minutes

Inventory working code. Create the agreed Pydantic types and service fake. Publish one typed `CompanyCaseView`, `OfficerCaseView`, `AnalysisView` and `RevisionResult` so D can work immediately. Publish the evidence and model adapter protocols for C and the deterministic-check inputs for B. No model or bank API is needed for the initial skeleton.

Verify that runtime API credentials actually exist, separately from coding-tool login. Do not use an interactive subscription session as an improvised inference endpoint. Keep secrets server-side and out of tracing.

## Build sequence

1. SQLite schema, immutable observations/documents, case versions and action receipts. Parameterized SQL only.
2. Role/enterprise scope at every service entry. Local actor switching is labelled demo impersonation; no public write deployment.
3. Read views and upload/context methods with limits. Nothing can choose scope from an uploaded MF.
4. LangGraph fixed nodes calling B/C functions. Use durable local checkpointer; graph state is not the authoritative case store. Keep checkpoint IDs private and case/actor/audience bound.
5. Company transcription confirmation and structured answers through service validation. Confirmation is not authenticity.
6. Officer-only clarification approval and local inbox publication. No real email/SMS/portal action.
7. Response proposal -> scoped officer acceptance -> atomic revision/recompute. Enforce expected version, quantity/payment budget and idempotency.
8. Redacted LangSmith instrumentation plus local event records. Hide raw inputs and outputs; whitelist metadata and sanitize errors. Trace outages cannot block writes.
9. Export scoped local draft, latest-version approval checks and tested restart/resume.

## Critical integration rules

No LLM call inside a SQL write transaction. A graph interrupt may replay code before it on resume: use pure nodes or action receipts. Before an acceptance commit, recheck actor, input hash and proposal scope. For an authorized exact retry, check the existing action receipt before rejecting the old expected version; a completed original action has already advanced that version. For new actions, enforce the expected version inside the write transaction. Do not trust a checkpoint or browser flag that says “approved.”

Do not catch and swallow LangGraph interrupts as normal exceptions. Resume with the installed library's documented API and write a restart test. All thresholds/financial logic come from B, not duplicated here or in the UI.

## Acceptance tests

Wrong company forbidden; company cannot approve its evidence; duplicate exact action returns prior outcome; same key/different payload fails; stale approval fails; record change invalidates old draft; timeout leaves facts unchanged; request stays a local demo action; trace payload excludes raw identifiers/docs; graph resume does not reapply an allocation.

## Hourly interfaces

Hour 1: imports and fake views usable. Hour 2: first real case analyzed. Hour 3.5: local clarification published. Hour 4.5: accepted response recalculates exactly once. Hour 5: freeze. Afterward only tests/fixes and release support.

## Done report

Report exact commands and results, changed types, migration instructions, provider/checkpointer modes, disabled features, and blockers. Do not claim production security or legal approval. Ask D to verify one full UI run independently.
