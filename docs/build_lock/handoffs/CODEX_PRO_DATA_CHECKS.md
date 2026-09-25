# Codex / Pro — Lane B: data, reconciliation, scenarios and evaluation

**Branch-start revision: V4-GIT-1.** This update adds branch execution, atomic commits and pushes. It does not change the product's eight-hour scope or replace the original lane responsibilities reproduced below.

## Assigned branch and startup prompt

**Model/workstream:** Codex / Pro  
**Lane:** `B`  
**Assigned branch:** `feat/checks-scenarios`  
**Remote:** the existing human-confirmed team remote, normally `origin`.  
**Integration branch:** `main` unless the human captain explicitly confirms the repository uses another base.

> Start implementing/reviewing the assigned V4 workstream now. Read this entire handoff and its shared dependencies. Work only on `feat/checks-scenarios` in your isolated repository checkout. After every coherent valid modification, run relevant checks, make an atomic commit and immediately push it to `origin/feat/checks-scenarios`. Do not wait until the workstream is complete. Keep source-safe commits scoped; never push directly to `main` or merge a PR without explicit human approval.

### Before editing

Read the repository's actual `AGENTS.md` first, then this build pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `GIT_WORKFLOW.md` and the module-specific documents below. The V4 eight-hour lock remains the product specification; older V1/V2/V3 plans are background, not another scope to implement.

The human must provide the complete pack in the repository. `PLAN_ROOT` is the pack location: repository root for a fresh project, or normally `docs/build_lock/` in an existing project. Documentation/fixture paths in this handoff are relative to `PLAN_ROOT`; implementation paths such as `boussla/` and `ui/` are relative to repository root. Do not copy an `AGENTS.md` over existing repository instructions without review. Missing documents or conflicting actual repository instructions must be reported, not silently invented/replaced.

Inspect the repository root, current branch, working-tree status, recent commits and remote. Confirm the remote is the intended team repository; never invent a GitHub URL, change visibility or log credentials from a remote URL. If no repository/remote is configured, ask the human captain for that one-time setup. Never replace `origin` or initialize a nested repository to make these commands appear to work.

### Branch creation/resume

Only after confirming the correct isolated checkout, a safe working-tree state and the authorized remote, use the following POSIX/Git Bash sequence (adapt syntax to your actual shell). If already on this branch with known in-progress work, preserve it and skip branch switching until a clean checkpoint.

```bash
BRANCH='feat/checks-scenarios'
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

**First milestone:** Implement the first pure invoice/settlement/quantity check from the supplied structured fixtures. Do not wait for PDF extraction, live Jev or the UI. Use A's types as soon as the foundation is published.

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
python -m pytest -q tests/checks/test_settlements.py
git diff --check

# Stage only files for that validated change.
git add -- boussla/checks/settlements.py tests/checks/test_settlements.py
git diff --cached --check
git diff --cached --stat
git diff --cached

# Commit only after the inspection and checks succeed.
git commit -m "feat(checks): distinguish partial payments from discrepancies"

# Publish only this branch; repeat after EACH valid atomic commit.
git push -u origin HEAD:refs/heads/feat/checks-scenarios

# Compare these SHAs before claiming the remote is up to date.
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/feat/checks-scenarios
```

Push rejection is not permission to force push. Fetch and inspect remote divergence with the owner. Synchronization commits must also be tested before push. Keep actual secrets, mutable runtime files and confidential material out of the entire outgoing diff/history, not merely out of the latest file view.

### Parallel-work boundary

Your functions accept explicit structured inputs and return A's typed contracts. They do not call providers, read the UI session or write case revisions. If a contract is unavailable, prepare fixtures/tests against the written contract and report the missing interface; do not create a permanent duplicate `Finding` or `ScoreResult` definition.

Publish callable names, one example input/output, actual test commands and the pushed SHA early. C supplies extracted candidate records later; A controls their accepted state. You never edit C's extractor or D's screens to make your tests pass.

## Suggested small commit milestones

These are examples, not permission to create empty commits or pretend a feature exists. Keep each actual commit internally coherent with its tests; split or combine only where needed for correctness.

| Example subject | Evidence before publication |
|---|---|
| `test(checks): add scoped fixture and comparability tests` | Tests/fixture contracts for the first supported case, without changing hidden expected answers to fit code. |
| `feat(checks): reconcile invoice observations and settlements` | Explicit origin, identity, basis, installment and missing-data behavior. |
| `feat(scenarios): enforce quantity allocation conservation` | Reallocation replaces the prior allocation; hypothetical margins never mutate accepted facts. |
| `feat(scoring): calculate V4 index and independent coverage` | Fixed V4 baseline and max-transaction aggregation; no inverse loyalty or delay penalty. |
| `test(evaluation): report supported and unknown-case outcomes` | Actual recorded scoped results; no invented extraction or fraud benchmark. |

## Original V4 implementation handoff — preserved below

Read shared instructions/contracts plus `docs/SCORING_AND_SCENARIOS.md` and `docs/DATA_AND_FIXTURES.md`. Do not rebuild A's service or D's UI. Your goal is trustworthy facts, not an impressive arbitrary fraud score.

## Own

`boussla/checks/`, `boussla/scenarios/`, `boussla/scoring.py`, `boussla/data/`, fixture-generation scripts, check/evaluation tests and `results/` calculation artifacts. Propose schema changes through A. Keep hidden oracle files out of app paths.

## First deliverable

Expose pure functions for invoice-observation comparison, settlement reconciliation, quantity allocation comparison, sensitivity scenarios, evidence-coverage calculation and company aggregation. Return the shared typed Finding objects with source IDs, exact amounts/units, prerequisite status and reasons. Start with included synthetic records and the reference tests.

## What to implement

- Normalize tax-ID formatting only; do not claim official validation or bank-account ownership.
- Match issuer + invoice number + date/version + buyer; don't use fuzzy similarity to override conflicting identifiers.
- Two observations of one sale are one transaction. Same file copy is not automatically fraud.
- Compare same currency and HT/TTC bases. Explicit net payable and settled allocations only; support the simple part-payment fixture or abstain.
- Verify project/item/unit/date scope and accepted procurement-allocation kind. A consumption or user estimate gives questions, not QUANTITY points.
- Allocation conservation: reassign quantities, do not add second-project allocation on top of the original full allocation; prevent duplicate units and amounts.
- Sensitivity scenarios are pure and labelled hypothetical. No simulation result writes canonical fields.
- Implement the fixed 35/25/40 baseline and max-transaction company policy, with partial/unknown coverage semantics. No loyalty, delay penalty, recursive score or model-confidence contribution.
- Distinct unresolved transaction count uses economic events, not number of uploads/reruns/question rounds.
- Display actual history from available snapshots. No filling past months with future facts or hidden labels.

## Data generator

Publish six showcase cases first, then a small linked history. Proposed scale only after integration: 50 companies, 12 months, 500–1,000 transactions. One underlying event ledger -> invoice/payment/declaration views, controlled delays and legitimate explanations. No independent random views that make every company inconsistent.

No government queries, RNE lookup, bank feed or automatic INS ingestion. Public legal documents do not label companies. If existing V3 LightGBM works, preserve separately; do not call this new rule baseline an ML score.

## Evaluation

Compare extraction-independent exact checks on known structured inputs, then end-to-end outputs on PDFs through C. Gemini/reviewer creates unseen variations without editing your tested logic. Group related versions/layouts together. Required negative cases: part payment, same-origin copies, missing source, wrong-company evidence, estimate-only quantity, late valid response, ambiguous units.

Measure exact arithmetic, linkage, false escalation of legitimate/unknown cases, actual document-field correctness supplied by C, and workflow outcomes. Do not claim an in-simulation gain establishes real tax-evasion detection. No arbitrary high accuracy target. `NOT_RUN` remains null/status, not zero.

## Output contract

`evaluate_transaction(inputs) -> findings`, `run_scenarios(inputs, config) -> scenarios`, `score_transaction(findings, applicability) -> ScoreResult`, `aggregate_company(transaction_scores) -> CompanyScore`.

Functions are deterministic, accept explicit as-of times and do not read global state. No network call, model call, clock read or random number inside score computation.

## Hour gates

Hour 1: first cases/functions. Hour 2: UI consumes reconstructible findings. Hour 3: hypothesis tests and data validation. Hour 4: independent suite. Hour 5: freeze and recorded results. End with exact pass/fail counts and limitations.
