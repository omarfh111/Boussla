# BOUSSLA final release — integration evidence

Branch `integration/final-release` from main `b33ae94`, merging lanes A (`874c718`), B (`07fdd00`), C (`2083312`) and D (`4559a7a`) with `--no-ff`. Synthetic data only.

## Judge gauntlet — round 2 (harness `test/live-judge-gauntlet` @ `159ef7b`, run against this branch)

| Outcome | Count |
|---|---:|
| PASS | 42 |
| SAFE_REJECTION | 6 |
| SAFE_FALLBACK | 2 |
| MANUAL_REQUIRED | 4 |
| BUG | 0 |
| NOT_RUN | 0 |

- 47 scenarios through the unmodified harness in live mode (providers configured privately): 36 PASS, 5 SAFE_REJECTION, 2 SAFE_FALLBACK, 4 MANUAL_REQUIRED, 0 BUG. Offline mode: 0 BUG as well.
- JUDGE-040…045 were `pending_context` stubs in the round-1 harness; a round-2 driver executed them against the integrated service (offline with an injected model disagreement, and live): 5 PASS, 1 SAFE_REJECTION (end before start). With a live model that agrees with the dates, JUDGE-045 correctly stays CONSISTENT; the disagreement path is proven with the injected run.
- JUDGE-046 (React/API/browser) is covered by the Playwright journeys: 8/8 offline and 8/8 live.
- Critical 0, High 0, Medium 0. Round-1 defects: LJG-001, LJG-002, LJG-003, LJG-004 and JUDGE-054 all pass (harness regressions and repository tests).

## Tests

- `python -m pytest -p no:cacheprovider`: 488 passed; with every non-loopback socket blocked: 0 external connection attempts.
- Frontend: typecheck, Prettier, 20 unit tests, production build; Playwright journeys 1–6 + boot + resilience, offline and live, each on a fresh disposable runtime.
- Public references: 29 reviewed passages, 4 official sources, hashes match. Qdrant `boussla_public_references_v2`: 29 points, 384 dimensions, Cosine, public payload only. Retrieval evaluation (21 fixed cases): top-1 16/21, top-3 19/21.

## Providers (live, synthetic data)

OpenAI extraction, context interpretation, investigator selection and grounded reference generation: LIVE. Jev routing: LIVE. Qdrant retrieval: LIVE. LangSmith: traces for `boussla.auto_clarification` and `boussla.investigator` (and the workflow nodes) with hidden inputs/outputs; no company names, tax IDs, invoice or purpose text, payment data or secrets found in metadata, tags or errors.

## Security

Company scope, operator-only administration, forged identity/score/triage/investigator fields (403), strict payloads (INVALID_INPUT), no `dangerouslySetInnerHTML`, no local paths in API responses, secret scan of tracked files, build output, screenshots and branch history: 0 matches.
