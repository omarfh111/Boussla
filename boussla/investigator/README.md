# Bounded officer investigation layer

`investigator_assistant().assess(data, audience=Audience.OFFICER)` returns an
`InvestigatorResult` with an optional officer-only `InvestigatorBrief`. Lane A
constructs `InvestigatorInput` from its authorized case view **after** checks,
scenarios, context assessment, history, clarification and public retrieval.
This package does not read or write case storage, accept evidence, publish
questions or recalculate findings or the review index. Do not give this brief
to the company audience.

Inputs are codes, scoped evidence references from accepted/assessed records, and deterministic hypothetical
scenario outputs. Lane A maps raw answers and transaction data to bounded
codes before calling this layer. The general OpenAI model receives only codes,
counts, and allowlists. It selects up to five fixed neutral hypothesis IDs and
up to three existing playbook question IDs. It writes no free-form case text.
An invalid response or provider outage falls back to a labelled `TEMPLATE`
brief. Company audience returns no brief. The assistant never automatically
publishes a question; Lane A retains the shared three-question merge budget.

Each observation is tagged `FACT`, `DECLARATION`, `MODEL_INTERPRETATION`, or
`HYPOTHETICAL_SCENARIO`. A hypothesis remains a candidate with explicit
supporting, contradicting and missing references. Support labels are simple
deterministic states, not probabilities. The scenario index, if supplied, must
come from Lane A/B's deterministic engine and is displayed as hypothetical.
Public reference IDs are candidates for officer review, never an automatic
legal conclusion. No part of this output feeds scoring.

Future Lane A wiring: construct the narrow DTO from officer-scoped data, call
`investigator_assistant().assess(dto, audience=Audience.OFFICER)` after the
deterministic checks and retrieval, and display `result.brief` only in the
officer dossier. Keep canonical writes and question publication in the
existing service/workflow. The typed `history_signal_codes` field accepts
bounded B-generated signal codes; it does not invent a new history store.
