> **V4-GIT-1 note:** the record below describes the original supplied build pack. This update preserved its code and fixtures and changed only collaboration documents/manifests. Current update checks and limitations are recorded separately in [BRANCH_PACK_VALIDATION.md](BRANCH_PACK_VALIDATION.md). No actual team remote was used.

# What was actually created and checked

**Date:** 25 September 2026. This file describes this build pack, not a completed BOUSSLA application.

## Created

- Final eight-hour product lock and common coding-agent instructions.
- Five separate coding/review handoffs for the four human workstreams and shared Gemini reviewer.
- Proposed data/service contracts; LangGraph/Jev/Qdrant/LangSmith architecture and source register.
- Document-integrity, scoring, scenario, security, release and presentation specifications.
- Candidate environment/dependency files. The full dependency environment is **not installed or tested** by this pack.
- Small standard-library reference functions and their tests.
- Eight fictional one-page native-text PDFs and their generator.
- Fourteen small observed seed files: three CSVs and eleven JSON files. Three synthetic enterprise entries, two projects and **one complete document-backed transaction/case**; this is not a large company-history dataset.
- Separate development oracle and test-variant descriptions, excluded from runtime ingestion.

## Executed locally

```bash
python -m unittest discover -s reference -p 'test_*.py' -v
python scripts/validate_fixture_pack.py --root .
```

**Reference tests: 30 passed.** They exercise the small pure-Python functions for decimal values, source-origin categories, scoring/unknown states, settlement examples, quantity budgets, scenarios and follow-up statuses. They do **not** establish application authorization, extraction accuracy, invoice authenticity or real-world fraud detection.

**Fixture validation: passed.** At the validation run, 15 input/config JSON files parsed; observed CSVs had 3 enterprise rows, 2 project rows and 5 source-coverage rows. Eight PDF file hashes matched the fixture inventory. Every PDF had one page, extractable text, the expected document ID and a prominent synthetic label. Quantity and monetary calculations matched their documented development oracle.

The sample before/after reference index of 40 and 0 comes from the explicit `CONTEXT_RULES_V4_1` heuristic under the accepted synthetic scenario, not from a trained risk model. The second state is tested by supplying its accepted facts; no application acceptance workflow has yet been executed.

**PDF visual check:** all eight PDFs were rendered with `pdftoppm` and visually inspected in a contact sheet. No clipping, overlapping text or broken glyphs was observed. Render previews are not included in the release ZIP.

**Pack checks:** Python files were byte-compiled for syntax; packaged JSON and file inventory were checked; no font binaries or actual API credentials are included. Byte-compilation is not an application integration test.

## Not executed / not supplied

| Item | Status |
|---|---|
| Finished Streamlit application and live company/officer workflow | NOT_BUILT |
| Production authentication, authorization and isolation | NOT_TESTED |
| LangGraph persistence, interruptions and concurrent retries | NOT_TESTED |
| Jev, general LLM or speech API calls | NOT_RUN |
| Qdrant ingestion/search and embedding-model download | NOT_RUN |
| LangSmith remote tracing/redaction | NOT_RUN |
| pyHanko/C2PA cryptographic or provenance validation | NOT_RUN |
| OCR, forged-document or AI-origin detector | NOT_RUN |
| Legal-text corpus with validated applicable rule cards | NOT_SUPPLIED |
| Taxpayer/regulatory/banking production data or connectors | NOT_SUPPLIED |
| Fifty-company historical dataset | TARGET_ONLY |
| Independent extraction/matching/workflow benchmark | TO_BUILD |
| Measured real-world fraud precision or money recovered | NOT_ESTABLISHED |
| Final 10–15-slide deck and two-page PDF synthesis | CONTENT_OUTLINE_ONLY |

The public technical references were consulted, but account entitlements, quotas and API behavior for the team must be verified with their own allowed credentials. There is no promise of free runtime inference, guaranteed winning or universal document authentication.

## Reproduction dependencies for the extras

The reference unit tests use only Python's standard library. Fixture validation additionally uses `pypdf`. Regenerating the sample PDFs uses `reportlab`; the script uses local DejaVu fonts if present and built-in Helvetica otherwise. Font files are not distributed. Changing fonts or regenerating PDFs can change their bytes; use the regenerated inventory rather than a stale hash.

See `reference/test_results.txt` and `reference/fixture_validation.json` for the actual recorded outputs. They remain development validation artifacts, not results to advertise as the integrated application's benchmark.
