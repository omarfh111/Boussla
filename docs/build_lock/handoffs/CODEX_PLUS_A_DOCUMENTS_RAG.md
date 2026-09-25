# Codex / Plus A — Lane C: document AI, Jev, Qdrant and provenance

**Branch-start revision: V4-GIT-1.** This update adds branch execution, atomic commits and pushes. It does not change the product's eight-hour scope or replace the original lane responsibilities reproduced below.

## Assigned branch and startup prompt

**Model/workstream:** Codex / Plus — document lane  
**Lane:** `C`  
**Assigned branch:** `feat/documents-rag`  
**Remote:** the existing human-confirmed team remote, normally `origin`.  
**Integration branch:** `main` unless the human captain explicitly confirms the repository uses another base.

> Start implementing/reviewing the assigned V4 workstream now. Read this entire handoff and its shared dependencies. Work only on `feat/documents-rag` in your isolated repository checkout. After every coherent valid modification, run relevant checks, make an atomic commit and immediately push it to `origin/feat/documents-rag`. Do not wait until the workstream is complete. Keep source-safe commits scoped; never push directly to `main` or merge a PR without explicit human approval.

### Before editing

Read the repository's actual `AGENTS.md` first, then this build pack's `AGENTS.md`, `01_FINAL_LOCK.md`, `contracts/CONTRACTS.md`, `GIT_WORKFLOW.md` and the module-specific documents below. The V4 eight-hour lock remains the product specification; older V1/V2/V3 plans are background, not another scope to implement.

The human must provide the complete pack in the repository. `PLAN_ROOT` is the pack location: repository root for a fresh project, or normally `docs/build_lock/` in an existing project. Documentation/fixture paths in this handoff are relative to `PLAN_ROOT`; implementation paths such as `boussla/` and `ui/` are relative to repository root. Do not copy an `AGENTS.md` over existing repository instructions without review. Missing documents or conflicting actual repository instructions must be reported, not silently invented/replaced.

Inspect the repository root, current branch, working-tree status, recent commits and remote. Confirm the remote is the intended team repository; never invent a GitHub URL, change visibility or log credentials from a remote URL. If no repository/remote is configured, ask the human captain for that one-time setup. Never replace `origin` or initialize a nested repository to make these commands appear to work.

### Branch creation/resume

Only after confirming the correct isolated checkout, a safe working-tree state and the authorized remote, use the following POSIX/Git Bash sequence (adapt syntax to your actual shell). If already on this branch with known in-progress work, preserve it and skip branch switching until a clean checkpoint.

```bash
BRANCH='feat/documents-rag'
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

**First milestone:** Deliver native-text PDF extraction and source passages for one included fixture, with a baseline parser and explicit unsupported states. Do not block the first integration on live APIs or a large corpus.

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
python -m pytest -q tests/documents/test_native_text.py
git diff --check

# Stage only files for that validated change.
git add -- boussla/documents/native_text.py tests/documents/test_native_text.py
git diff --cached --check
git diff --cached --stat
git diff --cached

# Commit only after the inspection and checks succeed.
git commit -m "feat(documents): extract native PDF text with page references"

# Publish only this branch; repeat after EACH valid atomic commit.
git push -u origin HEAD:refs/heads/feat/documents-rag

# Compare these SHAs before claiming the remote is up to date.
git rev-parse HEAD
git ls-remote --exit-code origin refs/heads/feat/documents-rag
```

Push rejection is not permission to force push. Fetch and inspect remote divergence with the owner. Synchronization commits must also be tested before push. Keep actual secrets, mutable runtime files and confidential material out of the entire outgoing diff/history, not merely out of the latest file view.

### Parallel-work boundary

Return candidate data, source passages, modes and errors through A's adapter protocols. Never accept evidence, set a financial score or create a second case database. Send dependency requests to A instead of editing shared requirement/lock files.

Bound the first Jev access/language check to the handoff's timebox. If access fails, ship and test the explicit fallback adapter, push that valid increment, and disclose `LIVE_API_NOT_TESTED` or the actual failure. Do not spend the integration window repeatedly requesting keys or claiming a hardcoded router is Jev.

Public reference ingestion requires inspected source text. Missing legal material is `NOT_SUPPLIED`, not permission to generate statutes. Runtime uploads, vector-store files, checkpoints and API payloads are excluded from commits.

## Suggested small commit milestones

These are examples, not permission to create empty commits or pretend a feature exists. Keep each actual commit internally coherent with its tests; split or combine only where needed for correctness.

| Example subject | Evidence before publication |
|---|---|
| `feat(documents): preserve originals and extract page text` | Hash/origin metadata and exact page spans; file limits; no authenticity claim. |
| `feat(documents): propose typed fields with evidence spans` | Known-layout parser baseline, missing fields remain null, candidate records only. |
| `feat(adapters): add bounded Jev routing with visible fallback` | Use actual authorized credentials when available; offline adapter tests never stand in for a live-provider test. |
| `feat(retrieval): search reviewed public references locally` | Qdrant local mode or a visibly labelled lexical fallback; no invented law corpus or random vectors. |
| `test(documents): reject unsupported spans and cross-company evidence` | Tests record actual modes, provider failures and source limitations. |

## Original V4 implementation handoff — preserved below

Read shared contracts and `docs/ARCHITECTURE.md`, `docs/DOCUMENT_INTEGRITY.md`, `docs/SOURCES.md`. Your module interprets documents; it never approves evidence or edits a score.

## Own

`boussla/documents/`, `boussla/adapters/`, `boussla/retrieval/`, extraction/router/RAG tests and small corpus-ingestion script. A owns graph orchestration/dependencies. Do not create a second service or database schema.

## First integration slice

Implement native PDF text extraction with pypdf and supported-size/page limits. Return page-indexed text and statuses. Implement deterministic extraction for the included known layout as baseline; then use one genuinely available model provider for candidate fields on layout variations. Exact spans and null for missing fields are required. Never use evaluation answer keys to return “extracted” fields.

The context's expected company is for comparison, not permission to fill an absent identifier into a PDF-derived field. Preserve both raw and normalized values. Unsupported scan -> labelled manual fallback unless a tested image/OCR adapter is already available. No repeated expensive OCR attempts.

## Jev

Use the official TypeSafe endpoint, verified request shape in `docs/SOURCES.md`, key from `TYPESAFE_API_KEY`, and configurable pinned version `JEV_MODEL`. Classify small text into invoice/credit-note/payment/allocation/delivery/other, or a purpose category. Return candidate class, actual model/version and source mode. Always include OTHER_OR_UNKNOWN. Do not ask Jev to calculate amounts/dates or decide fraud.

Run a tiny access/language smoke test within 15 minutes. Validate returned enums, finite confidence and type. On timeout/401/429/529 or low-quality results, route to explicit manual/rule fallback. Do not silently call fallback results Jev. Limit retries and do not log the key or raw sensitive text. Questions/prompts must treat documents as adversarial data, but prompting is not a security guarantee.

## Qdrant

Use local mode and one cached process resource. P0 public-law/reference collection only. Ingest 10–30 exact passages from team-supplied/official documents after source inspection, with source hash, title, date, page/article, jurisdiction, language and review status. Do not invent law text to fill the collection. Keep synthetic procurement policy out of the legal collection.

Test a locally cached multilingual embedding model; verify the exact supported name and dimension. Small chunks within its token limit. If download/model fails, lexical retrieval over the same corpus, labelled accordingly. No random embeddings. Financial matching stays in SQL/Python.

Return top candidate passage IDs, not a binding legal answer. Verify reference existence, case date/applicability bounds and source text. Unreviewed law applicability goes only to the officer as a candidate. No free-form legal deadlines in drafts.

## Integrity adapter

Required: SHA-256, original preservation, metadata inventory, signature presence if inspectable, format/processing limitations and source origin. Hash is not authenticity. AI-origin remains UNKNOWN unless a verified provenance claim supports a narrower report.

Optional after main slice: pyHanko configured signature validation; C2PA read/validation on formats you actually test. Distinguish unsigned, not checked, unsupported, invalid and valid-in-configured-context. Disable unsolicited network fetching. Don't train DocTamper or integrate a random free detector API tonight. No automatic financial-risk penalty from AI origin or metadata.

## Draft/extraction prompts

Use `config/prompt_templates.md`. Outputs reference allowed fact IDs. The renderer inserts amounts and source references; the model cannot invent them. Company and officer bundles are separately constructed by A before they reach your adapter.

## Acceptance

Actual extraction versus parser on the same test files, invalid span rejection, wrong-company fields not overwritten, ambiguous type fallback, real Qdrant query or labelled lexical mode, Jev provider-status evidence, no cross-company retrieval, no logs of secrets/raw files. Report integrations not executed and metrics not measured.
