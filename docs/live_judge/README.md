# Live judge gauntlet — Round 1

Test-only branch from main `320e36bdc1733e0e7097fff37406cd7ec040a4ee`.
**RED_UNRESOLVED — NOT READY TO MERGE.** Production fixes belong to A/C.

## Run

Use the project's requirements plus test tools `reportlab`, `python-dotenv`, `pytest`.
Live Qdrant also uses the existing optional `fastembed` dependency.
This run used Python 3.12.14 in `D:/hack_finance/.judge-venv`.

```powershell
python -m scripts.live_judge.pack
python -m scripts.live_judge.run --mode offline --all
python -m scripts.live_judge.run --mode live --scenario JUDGE-047,JUDGE-048,JUDGE-049,JUDGE-050,JUDGE-051,JUDGE-052,JUDGE-053 --env-file ../.env --update
python -m pytest -o addopts='' tests/live_judge/test_pack.py tests/live_judge/test_invariants.py
python -m pytest -o addopts='' tests/live_judge/test_regressions.py
```

The last command is intentionally red on the tested main. It is a regression gate,
not an expected-failure suppression. `--providers openai,jev,qdrant,langsmith`
selects live providers; absent configuration yields NOT_RUN or an explicitly observed fallback.

## Isolation and oracle boundary

Each scenario gets a new temporary SQLite database, upload directory, checkpoint
database and event log. The seed is synthetic and case/company IDs are remapped.
No normal demo database is opened. Process-restart tests share only their own
scenario's disposable directory. The public embedding model cache can persist;
it contains public model files. The Qdrant wrapper forbids collection mutations.

The generator has no random clock/UUID inputs; the fixed manifest seed is 32036.
Thirty deterministic document files include 28 valid PDFs and two deliberately
invalid PDF-labelled files. The oversized PDF and six-page PDF test upload limits.
ReportLab invariant mode fixes PDF metadata. Every valid document visibly says
synthetic/test-only and has synthetic metadata. No official seals or signatures.

`scenarios/`, `observed/` and `documents/` are runtime inputs. Expected outcomes
live only in `evaluation_only/`. Only the evaluator reads that directory. It passes
document text, bounded finding reasons or public passages to production adapters;
the answer-key object is never an adapter argument. Reports are evaluation output,
never runtime input. No fraud labels, accuracy claims or real taxpayer records.

Live HTTP audits keep request bodies in memory only and emit destination/status,
latency and privacy booleans. Private dotenv values, headers, error messages and
raw traces are not serialized. The report serializer scans configured API keys.
Synthetic LangSmith traces use the separate `boussla-live-judge-synthetic` project.

## Coverage and limits

54 scenarios cover deterministic findings, real SQLite/service/LangGraph,
malformed/oversized documents, role scope, double submit, concurrent clients,
process restart, provider chaos, model-output validation and live probes.
Core findings use already observed synthetic facts, so their success does not
claim successful OCR or end-to-end ingestion. Separate extraction/routing probes
exercise generated documents. Fault injection is explicitly offline.

Context consistency has six concrete prepared inputs and remains PENDING until
integration. React/API/browser interactions remain PENDING. No browser behavior
or HTTP authorization is inferred from service-only tests. PDF representative
two-column and dense layouts were rendered and visually inspected.

## Owner handoff

A: declaration-only evidence acceptance, allocation/context input validation.
C: definitive RAG applicability wording escaping validation.
D: consume the scenario manifest and isolated service setup for Round 2 HTTP and
browser tests after React/API integration. No production or frontend changes are
required to consume this test pack. A/C fix the reproduced defects centrally;
this lane reruns the same red tests afterward.

See `results/live_judge/report.json`, `report.md` and `bugs/` for measured results.
