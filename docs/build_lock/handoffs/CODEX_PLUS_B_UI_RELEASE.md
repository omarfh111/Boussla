# Codex / Plus B — Lane D: UI, integration visibility and release

**Branch-start revision: V4-GIT-1.** This update adds branch execution, atomic commits and pushes. It does not change the product's eight-hour scope or replace the original lane responsibilities reproduced below.

## Assigned branch and startup prompt

**Model/workstream:** Codex / Plus — UI lane  
**Lane:** `D`  
**Assigned branch:** `feat/company-admin-ui`  
**Remote:** the existing human-confirmed team remote, normally `origin`.  
**Integration branch:** `main` unless the human captain explicitly confirms the repository uses another base.

> Start implementing/reviewing the assigned V4 workstream now. Read this entire handoff and its shared dependencies. Work only on `feat/company-admin-ui` in your isolated repository checkout. After every coherent valid modification, run relevant checks, make an atomic commit and immediately push it to `origin/feat/company-admin-ui`. Do not wait until the workstream is complete. Keep source-safe commits scoped; never push directly to `main` or merge a PR without explicit human approval.

### Before editing

Read the repository's actual `AGENTS.md` first, then this build pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `GIT_WORKFLOW.md` and the module-specific documents below. The V4 eight-hour lock remains the product specification; older V1/V2/V3 plans are background, not another scope to implement.

The human must provide the complete pack in the repository. `PLAN_ROOT` is the pack location: repository root for a fresh project, or normally `docs/build_lock/` in an existing project. Documentation/fixture paths in this handoff are relative to `PLAN_ROOT`; implementation paths such as `boussla/` and `ui/` are relative to repository root. Do not copy an `AGENTS.md` over existing repository instructions without review. Missing documents or conflicting actual repository instructions must be reported, not silently invented/replaced.

Inspect the repository root, current branch, working-tree status, recent commits and remote. Confirm the remote is the intended team repository; never invent a GitHub URL, change visibility or log credentials from a remote URL. If no repository/remote is configured, ask the human captain for that one-time setup. Never replace `origin` or initialize a nested repository to make these commands appear to work.

### Branch creation/resume

Only after confirming the correct isolated checkout, a safe working-tree state and the authorized remote, use the following POSIX/Git Bash sequence (adapt syntax to your actual shell). If already on this branch with known in-progress work, preserve it and skip branch switching until a clean checkpoint.

```bash
BRANCH='feat/company-admin-ui'
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

**First milestone:** Build both views against A's labelled mock service immediately after the types are published. A readable upload → case → finding journey matters before visual polish or live model results.

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
python -m pytest -q tests/ui/test_company_view.py
git diff --check

# Stage only files for that validated change.
git add -- ui/company.py tests/ui/test_company_view.py
git diff --cached --check
git diff --cached --stat
git diff --cached

# Commit only after the inspection and checks succeed.
git commit -m "feat(ui): render company case from the shared service contract"

# Publish only this branch; repeat after EACH valid atomic commit.
git push -u origin HEAD:refs/heads/feat/company-admin-ui

# Compare these SHAs before claiming the remote is up to date.
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/feat/company-admin-ui
```

Push rejection is not permission to force push. Fetch and inspect remote divergence with the owner. Synchronization commits must also be tested before push. Keep actual secrets, mutable runtime files and confidential material out of the entire outgoing diff/history, not merely out of the latest file view.

### Parallel-work boundary

You own `app.py` and `ui/`; no other feature lane should rewrite them. Do not implement financial checks, a second extraction service or canonical case writes in Streamlit session state. A's service owns facts and permissions.

Keep fake/live/manual modes explicit. Replace the service adapter after integration, not the entire UI. Report missing service methods to A using an exact input/output example.

Reserve release time. Screenshots and measurements must come from the integrated tested commit, not a different mock view. Do not start a React migration or cloud-hosting detour. Do not automatically publish a public write-enabled demo or official-looking notification.

## Suggested small commit milestones

These are examples, not permission to create empty commits or pretend a feature exists. Keep each actual commit internally coherent with its tests; split or combine only where needed for correctness.

| Example subject | Evidence before publication |
|---|---|
| `feat(ui): render company and officer case views` | Minimal Streamlit tabs with synthetic-data and operating-mode labels. |
| `feat(ui): collect project context and show evidence sources` | Reuse project context, separate invoices/cash/declarations, no duplicated financial calculation. |
| `feat(ui): connect clarification and evidence review actions` | Call A's scoped service methods; UI state cannot authorize acceptance. |
| `feat(ui): show real revision changes and pending evidence` | Before/after facts come from the service, not scripted score animation. |
| `docs(release): document tested launch and demonstration path` | Real commands, known limitations and actual screenshots/results; no claimed exported artifact before checking it. |

## Original V4 implementation handoff — preserved below

Read shared contracts, `docs/DEMO_AND_PITCH.md` and `docs/TESTS_AND_8H_PLAN.md`. Own the interface, not financial logic. Build against A's service fake immediately; don't wait for model completion.

## Own

`app.py`, `ui/`, visual assets, UI smoke tests, run/readme instructions and release packaging. A owns requirements/contracts; request changes. Preserve a working current UI where possible. Default is Streamlit + Plotly, no new React migration.

## Screens in the same app

1. **Company — Mes opérations:** invoice upload, second supporting record or “not available”, purchase/sale history with separate invoiced versus observed-paid amounts.
2. **Company — Contexte et réponses:** reusable project form, intended use/beneficiary/horizon, at most three relevant questions, own clarification inbox and response upload.
3. **Officer — File de revue:** priority index, evidence coverage, active finding count, clarification status and source scope. No red “fraud” label or inverse loyalty.
4. **Officer — Dossier:** paired record comparison, source passages, original docs, explicit hypothesis matrix and sensitivity table; current case version and internal/recipient-safe draft tabs.
5. **Evidence review/history within dossier:** proposed versus accepted allocation, officer acceptance, actual before/after calculation, prior versions and stale approval notice.
6. **Diagnostics, secondary:** actual test metrics and LIVE/CACHED/MANUAL/TEMPLATE/NOT_RUN integration statuses. Do not imply developer expected outcomes are measured results.

Keep these as compact tabs/views, not six different applications. The main demo follows one case across two roles. A local actor selector must visibly say “simulation de rôles”; do not expose it as production authentication.

## Critical UX decisions

- The second invoice is not labelled “verified supplier evidence” just because the company uploads it. Show actual acquisition origin.
- A missing supporting file doesn't trap the user; allow an explicit pending/unavailable state.
- Ask project questions once, reuse context, confirm extracted critical values.
- “Short/long project” is context only, with exact dates shown. No automatic safe badge.
- Company sees only own information and officer-approved neutral questions; no internal ranking or counterparty tax status.
- Show file provenance separately from content match. “Unsigned” and “unknown origin” are not “fake.”
- Render the scenario as hypothetical until the officer accepts scoped evidence. Do not animate a made-up score drop.
- Display separate invoiced, settled and declared flows. Never add them together into an invented turnover total.
- Escape document text; no unsafe HTML from uploads. Do not iframe arbitrary file URLs or load images from third-party document links.

## Service usage

All writes call A's methods with actor, expected version and idempotency key. On conflict, refresh and request a new review. Button disabling is not the authorization boundary. Never set `accepted=True` or a score in session state as the authoritative change.

## Release

First working company-to-officer path by hour 2. Complete clarification/revision by hour 4.5. Freeze hour 5. Record actual demo, rehearse five-minute story, verify local startup/offline fallback and make code accessible. Use actual outputs for deck/note.

Prepare a 12-slide deck and maximum-two-page synthesis from `docs/DEMO_AND_PITCH.md`, but do not assert those artifacts exist until exported and opened. Work is shared: B verifies numbers, C sources/AI claims, A permissions/provenance, D final packaging. Submit by hour 7:15 or earlier official deadline; keep buffer.

No cloud-hosting repair may consume the submission buffer. No raw secrets, real taxpayer data or mutable globally shared public case journal. Report actual tested commands, UI flows and disabled features.
