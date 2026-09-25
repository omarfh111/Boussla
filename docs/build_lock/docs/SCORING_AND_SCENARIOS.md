# Deterministic scoring, history and scenario rules

These are prototype settings, not Tunisian statutory thresholds, calibrated probabilities or scientifically validated risk coefficients. Version all settings. Do not tune them until a preferred company becomes red.

## 1. P0 finding families

| Family | Max points | Prerequisites | Meaning |
|---|---:|---|---|
| COUNTERPARTY | 35 | Same transaction candidate; compatible bases; readable confirmed fields | Contradiction between invoice observations, not mere visual variation |
| SETTLEMENT | 25 | Explicit payable amount; matching payer/payee mapping; complete comparable settled allocations | Residual between documented payable and documented settlement at the tested stage |
| QUANTITY | 40 | Accepted procurement-allocation baseline; same item/unit/date/scope; accepted allocations budgeted once | Units assigned beyond the documented work-package allocation |

`severity` is within [0,1]. Counterparty identifier mismatch after disambiguation can be 1; amount severity can be `min(abs(gap)/max(reference_amount,1)/0.20,1)`. Settlement uses the same illustrative 20% scale only after its prerequisites. Quantity severity is `min(positive_excess/max(accepted_limit,1)/0.50,1)`. The 20% and 50% scales are experimental settings, not tolerances that authorize smaller mismatches. Display the actual gap even when severity is small.

Unknown prerequisites -> `INSUFFICIENT`, no fabricated zero observation. `NOT_APPLICABLE` is different from unavailable. A consumption estimate without procurement scope may produce a context question but no QUANTITY points. An unsupported free-text purpose mismatch likewise produces a review question, not an automatic penalty.

## 2. Transaction and enterprise score

```text
transaction_index = round_half_up(sum(weight_family * severity_family))
```

Only an evaluable `UNRESOLVED` finding contributes. Evaluable `EXPLAINED` has zero severity. Deduplicate by (transaction_id, family), keep the maximum supported severity within a family. A mismatch repeated in three differently worded findings counts once.

If no check is evaluable, index is `null`. If some are evaluable and others unknown, show the supported partial index with incomplete-coverage warning. Do not renormalize the missing families upward or describe the partial zero as proof of compliance. Lack of one unrelated source must not erase an independently supported discrepancy.

```text
enterprise_index = max(evaluable transaction indices in the selected scope)
```

This is a deliberately simple queue policy: one supported material issue is not diluted by uploading many small clean invoices. Show the scope and a separate count of **distinct currently unresolved economic transactions**. No recursive use of the prior enterprise score. No automatic moral trust score. Under P0, recurrence is a count/history signal, not extra points.

Do not aggregate incomparable “losses.” Quantity gaps are units; purchase prices are invoiced amounts; invoice-to-payment gaps are a settlement measure; none automatically equals tax loss.

## 3. Evidence coverage

For each known-applicable check, record evaluable/insufficient and the exact reason. A simple display is `100 × evaluable / known_applicable`, with numerator/denominator. Unknown applicability prevents a “complete” badge. A second-copy upload does not satisfy an independent-origin gate.

Coverage does not alter the risk index directly. It tells the reviewer how much of the intended comparison was possible. Company-facing document-completion status is separate from an officer's conclusion.

## 4. No inverse loyalty and no late-upload punishment

Why `loyalty = 100 - risk` fails as a design: it duplicates the same quantity, conflates uncertainty with behavior, and creates a feedback loop when repeated analyses are treated as fresh misconduct.

Keep these statuses instead:

```text
NOT_REQUESTED
AWAITING_RESPONSE
RESPONSE_RECEIVED
EXTENSION_REQUESTED
EXTENDED
FOLLOW_UP_DUE
CLOSED
```

A demo response target is not a tax-law deadline. Mark FOLLOW_UP_DUE only after a properly approved in-app request became available, the target passed, no response/extension holds it open, and service availability is adequate. Missing service/delivery metadata -> unknown follow-up status. Do not use latency, weak literacy, poor document format, device quality or response verbosity as risk features.

An answered request can still contain contradictory evidence; a delayed but well-supported response can explain the case. Wrongly flagged historical findings remain visible as prior system events, not repeated adverse facts after resolution.

## 5. Finite scenario design

Use a small grid of *explicit* assumptions, not repeated LLM guesses:

1. Baseline using currently accepted procurement allocation.
2. Sensitivity at +10%, labelled fictional, not an authorized increase.
3. Candidate second-project allocation, shown separately until accepted.
4. Accepted second-project allocation, after service validation, used for actual recalculation.

For the demonstration, a purchase contains 2,000 units. The accepted first-work-package allocation is 1,000. Before reassignment, the observed assigned quantity is 2,000. Baseline excess is 1,000; the +10% hypothetical envelope yields 900. Neither is “money stolen.”

A response proposes 1,000 units for another approved work package. After acceptance, update the allocation ledger to 1,000 + 1,000 with shared quantity-budget checks; do not simply add another allocation to the original 2,000. The first-work-package finding then resolves under the supported scenario.

Total accepted allocations plus accepted returns cannot exceed available eligible receipt quantities. Warehouse allocation must not be double-counted later when the same units are assigned to a project; use explicit transfer/reclassification links.

For P0 reject complex incompatible-unit or partial-delivery cases with a clear limitation, rather than silently infer a conversion or assume full delivery. Show “comparison not performed” for those cases.

## 6. Horizon semantics

Store planned and revised dates, source, author and available timestamp. A longer project can explain continuing inventory or future scheduled consumption, but does not prove either. Do not linearly prorate bricks by elapsed time without a provided schedule.

The AI chooses context-question families; code computes elapsed time. A user changing the expected end date must not erase an invoice mismatch or reset a response target. An accepted revised plan may change an allocation comparison, with explicit audit history.

## 7. Optional learned model

A learned classifier is outside the critical eight-hour path. If the existing LightGBM pipeline works, keep it as `TAX_SCREENING_V3` with its actual provenance; the new context checks remain `CONTEXT_RULES_V4`. Do not arbitrarily add points to its output.

If adding a model later, collect independent outcomes and observational features, use enterprise/group splits, keep repeated versions together, and compare against the same-information rule baseline. A model learning this exact scoring formula from synthetic labels adds no independent detection evidence. The six showcase cases are not a held-out fraud benchmark.
