# BOUSSLA — Progressive review and separate indicators

## Intent and scope

This specification covers the first delivery of the approved roadmap: business calculations and their presentation in the existing officer dossier. It does not redesign the company journey or build the network view. The goal is to make the existing document → reconciliation → analysis → explanation → new evidence → human decision path understandable in a live demo.

The user approved a review index that decreases before officer acceptance, provided each decrease is tied to a specific cause and clearly marked provisional. The frontend never calculates a score or chooses a progression stage. Every number, stage, contribution, reason and projected impact displayed by the frontend comes from the backend.

This is a local, synthetic demonstration. None of these indicators is a fraud probability, a legal conclusion or an authenticated statement about a real company.

## Current system and boundaries

- `boussla/checks/` produces deterministic `Finding` records for counterparty, settlement and quantity checks. `boussla/scoring.py` weights these families 35/25/40, aggregates by maximum transaction index and calculates evidence coverage.
- `boussla/services.py` owns case revisions, response and document links, evidence proposals, officer acceptance, queue data and audience-specific views. SQLite stores versioned facts and score snapshots.
- `boussla/triage.py` adds operational urgency from the review index, pending work and historical signals. Historical signals are neutral observations about the company's own covered history.
- The company API view has no internal findings or scores. The officer view and queue may receive the new indicators.
- The old `docs/build_lock/` documents describe the finished hackathon V4 scope. This newer user-approved design intentionally changes the review-index semantics and introduces operational confidence. Other provenance, role and human-decision safeguards remain in force.

## Progressive review calculation

Each supported unresolved finding becomes a cause keyed by `(transaction_id, family)`. Its **raw contribution** is the existing family weight multiplied by severity, using decimal arithmetic. Findings with missing prerequisites or insufficient information produce no adverse contribution. Existing finding statuses and underlying observations are not rewritten to make progress appear real.

The backend derives one stage for each cause from facts in the same case version:

| Stage | Qualifying state | Remaining contribution | Example from raw 40 |
|---|---|---:|---:|
| `UNRESOLVED` | Supported unresolved cause | 100% | 40 |
| `EXPLANATION_RECEIVED` | Nonempty response to a question explicitly linked to the cause | 75% | 30 |
| `EVIDENCE_RECEIVED` | Readable, scoped document attached to that response and linked to the cause | 50% | 20 |
| `EVIDENCE_COHERENT` | Deterministic checks of the linked proposal, extracted or confirmed fields and document provenance find no relevant contradiction | 25% | 10 |
| `RESOLVED` | Officer accepts the scoped evidence and the underlying finding resolves | 0% | 0 |

The 25% stage means **technical consistency in this dossier**, not authenticity. An LLM classification, PDF hash, absence of a signature or model confidence alone cannot grant it. If the necessary fields cannot be verified, the stage remains `EVIDENCE_RECEIVED` and the missing check is shown. A document's arrival alone can never produce `RESOLVED` or an index of 0 while a supported cause remains unresolved. A new contradictory document or answer can revoke an earlier provisional stage, moving the cause backward and raising its contribution and the index; the dossier records which source and check caused the regression. Rejecting evidence likewise removes the provisional reduction supported by that evidence; another independently linked response may still support its own stage. A stale response, document from another company, duplicate retry or response to another cause never changes this cause's stage. The stage is recomputed from versioned facts, not incremented from an in-memory counter.

The public officer score contract adds a cause list with raw contribution, current contribution, stage, provisional flag, reason code and source IDs. It also exposes `raw_review_index` and `review_index`. For each transaction, the backend sums its distinct family contributions and caps at 100. The case index remains the maximum transaction index; the cause list identifies the transaction that determines that case index, so displayed contributions can be reconciled with the number. Decimal contributions are rounded only at the final index, with a minimum of 1 while a supported cause is unresolved. The existing family weights and evidence-coverage formula remain versioned and separate. The existing `contributions` field retains its raw family values for compatibility; the new cause list is authoritative for progressive values. The method ID changes so old and new snapshots are not silently compared as one method.

An accepted change may also alter the underlying deterministic finding. The final index is recalculated from the new accepted facts; it is not forced to zero. If the finding remains unresolved after acceptance, the new raw finding governs and the dossier explains the residual contribution.

## Indicators and historical context

The officer dossier presents five independently labelled outputs:

1. **Documentary review index:** progressive, per-cause contributions and provisional states; never a fraud probability.
2. **Historical signals:** codes, observed value, own-company baseline, covered periods and source IDs. No cross-company comparison or automatic adverse finding.
3. **Evidence coverage:** the existing percentage and unknown prerequisites; completeness is not low risk.
4. **Operational urgency:** the existing triage formula, with separate reason components. Historical signals may change triage, not the documentary review index.
5. **Operational confidence:** an officer-only 0–100 demonstration indicator of the reliability of interactions and corroboration. It is neither `100 - review_index` nor an input to review index, finding status, case decision or triage.

Operational confidence uses four explicit dimensions: response timeliness against *published demo targets* including unanswered requests after the target (30%), coherence of answers with verifiable dossier facts (25%), accepted versus rejected scoped documents (25%), and repeated documented inconsistencies in covered history (20%). Timeliness is on-time responses divided by requests whose target has passed or that were answered; answer coherence is deterministically consistent answers divided by answers for which a deterministic comparison is possible; evidence corroboration is accepted divided by accepted plus rejected scoped proposals; historical stability is one minus the share of distinct covered transactions with repeated supported invoice conflicts. Each is scaled to 0–100 and carries its numerator, denominator, reason codes, source IDs and weighted contribution. A dimension with denominator zero is omitted and the remaining weights renormalized. Fewer than three eligible observations overall returns `null` with `INSUFFICIENT_DATA`, not an invented default score. A pending request before its target and missing historical coverage are unknown, not negative. The calculation is versioned and recalculated from stored facts at a declared cutoff: later corrections, accepted evidence or newly covered history can raise or lower it, with factor-level before/after deltas in the officer history. A late upload by itself is not a financial finding.

Historical analysis compares the enterprise with its own completed, covered months only. Extend the current signals for unusual document arrival delay relative to its baseline, invoice frequency and amount changes, new or newly concentrated suppliers, observed settlement-ratio changes, unusual split settlement patterns, and repeated invoice inconsistencies. Every signal carries the threshold, baseline window, coverage and source IDs. Missing months are not imputed as zero; mixed currencies are not combined. Signals feed the operational urgency through bounded, deduplicated reason codes. Thresholds are versioned demo conventions, not legal deadlines.

A lone buyer invoice is `AWAITING_COUNTERPARTY` / « En attente de rapprochement » in the officer explanation. It has no counterparty discrepancy contribution. When an independently sourced seller observation is available and unambiguously linked, the deterministic comparison produces either a supported difference or a documented match. Merely uploading a second company-supplied copy does not establish independence.

## Data flow and UI contract

The backend returns one version-consistent officer summary from `get_case` and queue reads. It contains the five indicators, the cause contributions, missing prerequisites and a short ordered list of next actions derived from reason codes (for example: request a document, clarify a quantity, inspect a payment, or submit evidence for officer review). Actions are recommendations, never automatic administrative decisions.

“Impact if resolved” uses the same backend calculation on a copy of the current case facts. It reports the current index, projected index, assumptions, causes affected and evidence/decision still required. It never writes canonical facts and never presents a hypothetical reduction as already achieved. The existing scenario view may consume this result; TypeScript renders the values exactly as returned. The current dossier gets a compact indicator strip and cause table so the first delivery is demonstrable without the later navigation redesign. Internal indicators remain absent from `CompanyCaseView` and company API responses.

On every relevant write, the service persists the new facts and the recalculated score snapshot in one case revision, preserving idempotency and expected-version checks. Read-time triage and historical signals carry an `as_of` timestamp. Provider failures fall back to deterministic/manual states; they never lower a contribution or create a finding. Invalid or ambiguous links leave the stage unchanged and return a clear reason.

## Verification and acceptance

- The showcase quantity cause moves through 40 → 30 → 20 → 10 → 0 on five successive, versioned states with exact source links. Each stage and provisional label is returned by the backend; the UI performs no score arithmetic.
- Unrelated response, missing/foreign document, contradictory extraction, rejected evidence, stale version and repeated idempotent request cannot earn an unjustified stage. A new contradiction after `EVIDENCE_COHERENT` moves the cause back and raises the index with an explicit reason.
- Officer acceptance recalculates actual findings and preserves old score snapshots. An accepted but still unresolved cause retains its residual index.
- A lone buyer invoice is pending; an independent seller observation triggers comparison; same-origin copies do not.
- Historical signals and operational confidence never alter the documentary review index. Missing coverage or too few confidence observations yield explicit unknown states. Every confidence change exposes its factor-level before/after values and source IDs.
- The company API contains no internal score, triage, historical ranking or confidence fields. The officer sees the five separate indicators and their explanations.
- Python unit/integration tests, frontend unit/typecheck/build and the existing demo browser journey verify the release. Tests use synthetic fixtures and no live provider dependency.

## Later deliveries

The second delivery redesigns the agent dossier and company workflow around the same backend contracts, then expands dynamic questions, per-document analysis, notifications and timeline. The third delivery adds the 3D investigation graph after relation data is stable; it reads the same server-owned indicators and never duplicates score logic. Each later delivery receives its own focused design and plan before implementation.
