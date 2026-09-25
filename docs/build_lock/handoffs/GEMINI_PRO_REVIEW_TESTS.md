# Gemini Pro — independent reviewer, not a fifth uncontrolled writer

**Branch-start revision: V4-GIT-1.** This update adds branch execution, atomic commits and pushes. It does not change the product's eight-hour scope or replace the original lane responsibilities reproduced below.

## Assigned branch and startup prompt

**Model/workstream:** Gemini / Pro — independent reviewer  
**Lane:** `REVIEW`  
**Assigned branch:** `test/independent-review`  
**Remote:** the existing human-confirmed team remote, normally `origin`.  
**Integration branch:** `main` unless the human captain explicitly confirms the repository uses another base.

> Start implementing/reviewing the assigned V4 workstream now. Read this entire handoff and its shared dependencies. Work only on `test/independent-review` in your isolated repository checkout. After every coherent valid modification, run relevant checks, make an atomic commit and immediately push it to `origin/test/independent-review`. Do not wait until the workstream is complete. Keep source-safe commits scoped; never push directly to `main` or merge a PR without explicit human approval.

### Before editing

Read the repository's actual `AGENTS.md` first, then this build pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `GIT_WORKFLOW.md` and the module-specific documents below. The V4 eight-hour lock remains the product specification; older V1/V2/V3 plans are background, not another scope to implement.

The human must provide the complete pack in the repository. `PLAN_ROOT` is the pack location: repository root for a fresh project, or normally `docs/build_lock/` in an existing project. Documentation/fixture paths in this handoff are relative to `PLAN_ROOT`; implementation paths such as `boussla/` and `ui/` are relative to repository root. Do not copy an `AGENTS.md` over existing repository instructions without review. Missing documents or conflicting actual repository instructions must be reported, not silently invented/replaced.

Inspect the repository root, current branch, working-tree status, recent commits and remote. Confirm the remote is the intended team repository; never invent a GitHub URL, change visibility or log credentials from a remote URL. If no repository/remote is configured, ask the human captain for that one-time setup. Never replace `origin` or initialize a nested repository to make these commands appear to work.

### Branch creation/resume

Only after confirming the correct isolated checkout, a safe working-tree state and the authorized remote, use the following POSIX/Git Bash sequence (adapt syntax to your actual shell). If already on this branch with known in-progress work, preserve it and skip branch switching until a clean checkpoint.

```bash
BRANCH='test/independent-review'
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

**First milestone:** Inspect a specified commit/diff; write independent scenario expectations and the first reproducible review finding. You are not a fifth production-code owner.

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
git diff --check
git diff --check

# Stage only files for that validated change.
git add -- reviews/gemini/initial-review.md
git diff --cached --check
git diff --cached --stat
git diff --cached

# Commit only after the inspection and checks succeed.
git commit -m "docs(review): record inspected snapshot and reproducible blockers"

# Publish only this branch; repeat after EACH valid atomic commit.
git push -u origin HEAD:refs/heads/test/independent-review

# Compare these SHAs before claiming the remote is up to date.
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/test/independent-review
```

Push rejection is not permission to force push. Fetch and inspect remote divergence with the owner. Synchronization commits must also be tested before push. Keep actual secrets, mutable runtime files and confidential material out of the entire outgoing diff/history, not merely out of the latest file view.

### Narrow review-write permission — explicit update

You may create and modify **only** `reviews/gemini/`, `tests/review/` and small synthetic files under `fixtures/review/` on `test/independent-review`. This is the one amendment to the previous read-only default: tests/reports now have a publication branch. Production modules, shared fixtures/oracles, schemas, dependencies and other owners' handoffs remain read-only unless the named human owner explicitly authorizes a particular patch.

Do not copy expected answers into runtime inputs or edit B's generator to make your results favorable. Keep reviewer-only oracle files out of runtime ingestion. Record the exact inspected commit separately from the commit publishing your review.

**Red regression-test exception:** a correctly constructed test that reproduces an existing defect can be committed and pushed on this review branch, accompanied by the actual failing output and `RED_UNRESOLVED — NOT READY TO MERGE`. Confirm the failure is the target defect, not a missing dependency or broken test. Do not mark it passing, delete the assertion or merge failing review tests into `main` without the corresponding fix. Tests that cannot execute are `NOT_EXECUTED`, not successful reproductions.

If your Gemini interface has no repository, terminal or push capability, return review text and a patch to the assigned human. The human uses this review branch to run and publish it. Never pretend to have executed Git or tests, and never ask for account credentials in chat.

## Suggested small commit milestones

These are examples, not permission to create empty commits or pretend a feature exists. Keep each actual commit internally coherent with its tests; split or combine only where needed for correctness.

| Example subject | Evidence before publication |
|---|---|
| `docs(review): record baseline and untested boundaries` | Name the reviewed SHA, actual commands/results and unavailable execution capabilities. |
| `test(review): add independent invoice and allocation scenarios` | Small synthetic variants not copied from runtime answer keys; use neutral IDs. |
| `test(review): reproduce authorization and retry edge cases` | Cross-company, stale-version, duplicate and allocation-conservation checks. |
| `docs(review): audit provider modes and evidence claims` | Differentiate actual live calls, mocks, fallbacks and NOT_EXECUTED tests. |
| `docs(review): report final blockers for the integrated release` | Reproductions, minimal fixes and named owners; no new features. |

## Original V4 implementation handoff — preserved below

Read `AGENTS.md`, the final lock, shared contracts and the actual code/diffs supplied by a human. You support the four-person team. You do not get permission to modify every module, acquire accounts, run public-system requests or invent passed tests.

## First task: challenge the proposed behavior

Inspect specifically: same-origin invoice copies; invoice-versus-cash confusion; unauthenticated fiscal IDs; self-reported purpose promoted to fact; long projects treated as safe; simulated quantity margins treated as real authority; inverse loyalty; late-response penalties; AI-origin used as fraud proof; cross-company information leakage.

Return concrete failures and minimal fixes, not another product idea. The team has eight hours, with feature freeze at hour 5.

## Independent fixture design

Prepare 10–15 new small scenario variations not used to tune extraction, without editing B's generator or reference results. Use neutral IDs. Include matching different-layout invoices, wrong supplier same amount, partial payment, duplicate observation, future-dated arrival, user estimate-only quantity, additional allocation for another transaction, overallocated quantities, source outage, delayed valid reply and a malicious instruction in a document.

For each, give supplied observations, explicit assumptions, expected supported finding or unknown status and why. Do not invent Tunisian statutory deadlines, technical construction norms or legally mandated invoice counts.

If you cannot execute code in your environment, produce test cases for the lane owner and mark `NOT_EXECUTED`. A review comment is not a passing test.

## Adversarial code review

Inspect the actual service call path. Company A must not read B's data or approve evidence. Prompts/retrieval must be scoped before model calls. An app restart/retry cannot double-apply allocations. Stale-version approvals fail at the service, not only the UI. Logs must not contain keys, raw tax identifiers or documents.

Check exact arithmetic, quantity budget, event deduplication, missingness, scenario purity, score reconstruction and no historical feedback loop. Verify that live Jev/Qdrant/LangGraph/LangSmith claims correspond to real run evidence. Check fallback modes; no fake model wrappers around hardcoded expected outcomes.

## Source review

Check quotations against actual ingested text/page references, dates/scope and reviewer status. Distinguish law from fictional procurement policy. The team's source permissions, official-registration status and legal acceptance are questions for the mentor, not conclusions an LLM can supply.

Do not perform an indiscriminate legal research expansion. Review only the rules actually shown in the demo. Remove unsupported claims instead of replacing them with plausible articles.

## Pitch review

Using actual app screenshots/results, test whether a nontechnical teammate can explain the product in 30 seconds. Flag any claim of guilt, money recovered, guaranteed win, universal forgery detection, production security, statutory legitimacy or model superiority that lacks evidence.

Provide 10 likely jury questions and short factual answers. Review the final note for two-page fit after the team's actual export; do not say it is two pages merely because the text looks short.

## Output format

Return a table: severity BLOCKER/MAJOR/MINOR; file/function; reproduction; expected versus actual; minimal proposed fix; owner; execution status. Lead with the three defects most likely to break the demonstration. No new framework or refactor after hour 5.
