# Project context consistency core

This isolated layer checks a company's declared project context. It returns
neutral clarification candidates; it never changes findings, evidence status,
the review index, or the declaration itself.

## Separate sources of meaning

- **DECLARED:** `ContextInput` copies the purpose, dates, stage, beneficiary type,
  and declared horizon from company context. `ContextInput.from_claim()` copies
  only those fields from the richer `ContextClaim`; Lane A supplies the horizon
  separately until its shared contract gains that field.
- **INTERPRETED:** the configured general OpenAI model suggests a purpose category
  and horizon from `purpose_text`. Every supporting span and explicit duration
  phrase must be an exact substring. Invalid output or provider failure returns
  `UNKNOWN` with `TEMPLATE` or `NOT_RUN`, without an adverse finding.
- **CALCULATED:** pure code subtracts `planned_start` from `planned_end`. A same-day
  interval is 0 days. `DEMO_SHORT_HORIZON_MAX_DAYS = 90` lives only in
  `duration.py`: 0–90 days is `SHORT_HORIZON`; 91+ is `LONGER_HORIZON`. Missing
  dates are `UNKNOWN`; reversed dates are explicit insufficiency.
- **CORROBORATED:** `NOT_ASSESSED` in this core. Model interpretation and a
  company declaration cannot corroborate themselves. Lane A's existing
  accepted-evidence workflow remains the only place for future corroboration.

These buckets are a BOUSSLA demonstration convention, not a legal, tax,
accounting, risk, or fraud classification. A longer project does not by itself
add questions. Missing or conflicting relevant context produces reason codes.
`reference_expected=True` is a trusted caller signal for cases where a project
or allocation reference is applicable; otherwise a missing reference is not
questioned. Recommendations are fixed French question IDs, deduplicated and
capped at three per round. No model writes question text.

## Narrow Lane A handoff

```python
from boussla.context.assistant import context_consistency_assistant
from boussla.context.models import ContextInput, HorizonBucket

context = ContextInput.from_claim(
    context_claim,
    declared_horizon=HorizonBucket.SHORT_HORIZON,  # confirmed company value
    project_reference=confirmed_project_reference,
    reference_expected=reference_is_applicable,
)
assessment = context_consistency_assistant().assess(
    context, answered_question_ids=answered_question_ids,
)
# Read assessment.interpretation, assessment.duration_days,
# assessment.calculated_horizon, assessment.consistency.status,
# assessment.reason_codes, assessment.recommended_question_ids, assessment.mode.
```

Lane A must add or obtain a confirmed `declared_horizon` without deriving it from
the model; add the new IDs/text from `questions.py` to its shared playbook; and
combine these recommendations with its existing question planner under the
overall three-question limit. Run the assessment after context entry and normal
deterministic checks. Never pass it to scoring or treat a mismatch as a finding.
Lane D may later display declared, interpreted, calculated, and corroboration
states separately with neutral clarification wording. No service, workflow,
playbook, UI, or scoring file is changed in this branch.

The model payload contains only `purpose_text`, declared purpose category and
horizon, planned start/end, and stage. It omits company IDs, tax IDs, amounts,
payments, beneficiaries, project references, findings and review priority.
Lane A must ensure user prose itself is suitable for the model before calling
this layer; the core cannot identify arbitrary company names embedded in prose.
No purpose text is logged as telemetry metadata.
