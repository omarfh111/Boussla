# Backend integration guide (lane A)

Shared types: `boussla/contracts.py`. Contract changes go through lane A (`docs/build_lock/handoffs/CHANGE_REQUESTS.md`).

## Setup

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Copy `.env.example` to `.env` (git-ignored) and fill in only what you use. With no `OPENAI_API_KEY`, the planner falls back to deterministic questions (mode `TEMPLATE`). With no `LANGSMITH_API_KEY`, only the local `runtime/events.jsonl` trace is written. Runtime state (`runtime/`) is ignored; delete it to reset the demo.

## D — UI

| Need | Import |
|---|---|
| Fake service (in-memory, everything `MOCK`) | `from boussla.mock_service import MockBousslaService, demo_actors` |
| Real service (SQLite, seeded demo case) | `from boussla.services import build_service` |
| Graph-driven analysis/decisions | `from boussla.workflow import build_runner` |

Both services implement `contracts.BousslaService`, so switching is one line. Actors come from the server roster (`service.registry.actors`: `DEMO-COMPANY-BAT`, `DEMO-COMPANY-OTHER`, `DEMO-OFFICER`). A forged role or company raises `FORBIDDEN`.

- Every write needs `expected_version` (from the last view's `case_version`) and a unique `request_id`/`idempotency_key` per user action. Reuse the key when retrying the *same* click.
- On `BousslaError` with `code == STALE_REVISION`, reload the case and ask the user to review again.
- Company flow with questions: `runner.run_analysis(actor, case_id, version)`, then `runner.submit_answers(actor, case_id, {question_id: text})`.
- Officer decision: `runner.open_decision(officer, case_id, proposal_id, version)`, then `runner.decide(officer, case_id, proposal_id, accept=True|False, reason=...)`. You can also call `service.accept_evidence` / `reject_evidence` directly.
- Response with reallocation: `service.submit_response(company, case_id, request_id, {"answers": {...}, "document_ids": [...], "allocation": {"transaction_id": "TX-001", "line_id": "LINE-BUY-001", "splits": {"P1": "1000", "P2": "1000"}}}, version, key)`. This only creates a proposal; nothing changes until an officer accepts it.
- Show `banner_fr` permanently, and show `mode` / `mode_by_node` honestly (`LIVE`, `TEMPLATE`, `NOT_RUN`, `MOCK`).

## B — checks

Provide a module `boussla/checks/__init__.py` exposing module-level functions matching `contracts.ChecksEngine`:

```python
def evaluate_transaction(inputs: TransactionInputs) -> list[Finding]: ...
def run_scenarios(inputs: TransactionInputs, config: dict) -> list[Scenario]: ...
def score_transaction(findings: list[Finding], applicability: set[FindingFamily]) -> ScoreResult: ...
def aggregate_company(transaction_scores: list[ScoreResult]) -> int | None: ...
# optional: test_hypotheses(inputs, findings, pending_second_package=False) -> list[Hypothesis]
```

`interim_checks.get_checks_engine()` switches to your module automatically as soon as it satisfies the protocol. Until then, the service uses `InterimChecks`, which is labelled with `calculation_version=INTERIM-A-GLUE+PACK-REFERENCE-...`. `tests/backend/test_interim_checks.py` and `test_services.py` are the regression bar your engine should also pass.

## C — documents/adapters

The service accepts injected adapters implementing `contracts.TextExtractor` and `contracts.FieldExtractor`:

```python
BousslaAppService(store, text_extractor=..., field_extractor=...)
```

They run **before** the write transaction on upload. A resulting `ExtractionProposal` is stored and shown to the company for confirmation (`confirm_transcription`). Adapter exceptions become "no extraction" (manual path), never findings. Tell A which factory to import and A will wire it into `build_service()`.

## Guarantees and limits

- Writes are atomic (`BEGIN IMMEDIATE`). Identical retries replay the stored receipt. Stale new actions fail. No model call runs inside a transaction.
- Facts are append-only, and any past version is reconstructible (`store.facts(..., version=n)`).
- The LangSmith trace has empty inputs and outputs and whitelisted metadata only (hashed case ref). This was verified against a live LangSmith project.
- Local role simulation is not authentication. Request publication is in-app only (no email or SMS). Logs are not tamper-proof legal evidence.
