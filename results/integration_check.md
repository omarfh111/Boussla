# Temporary A+B integration check — 2026-09-25

This check combined lane A's `feat/backend-workflow` at `0141ffb` with lane B's
`feat/checks-scenarios` at `4e9fd08` in a temporary file snapshot. The Git
merge preview was conflict-free (`git merge-tree --write-tree`). Neither
branch nor `main` was merged or changed for this test.

The snapshot ran lane B checks, lane A backend and workflow tests, and the
pack reference suite: **174 passed, 0 failed in 5.80s**. Lane A's service
factory discovered `ChecksEngineV4`, and its seeded case, clarification,
acceptance, and workflow regression tests passed with lane B's engine present.

The isolated test environment used pytest 9.1.1, Pydantic 2.13.5, LangGraph
1.2.12, and langgraph-checkpoint-sqlite 3.1.1. The temporary snapshot was
removed after validation. The lane B branch itself remains clean and pushed.

This establishes compatibility for the exercised synthetic local flows. It
does not test PDF extraction, Jev, Qdrant, Streamlit, live providers, or a
reviewed merge into `main`. At this check, `main` still pointed to the initial
commit `19c94a8`; lane A's foundation must be reviewed and integrated before
lane B can open a focused PR against `main`.
