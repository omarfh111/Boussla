# Included fixture scope

These are **synthetic development inputs**, not real invoices, bank records, signatures, tax identities or a held-out fraud benchmark.

Exactly one complete document-backed case is supplied, with eight one-page native-text PDFs. The six showcase cases in the plan are implementation targets; the alternative inputs/expected outcomes are described in `evaluation_only/expected_outcomes.json`, not six already implemented application workflows.

Load only the first five documents into the initial case. Keep the proposed reallocation unavailable until the company responds. Keep the conflicting view and adversarial instruction out of the main case unless running their dedicated tests.

The seller-view fixture has a separately assigned **simulated source origin**. All PDFs in this pack were created by the same generator. They do not establish independent real-world provenance. If a user uploads both PDFs, the service must classify both as company uploads, overriding any suggestive filename/content.

A reported P1 allocation is accepted as the company's statement, **not proof of physical use**. The finding is a discrepancy between reported allocation and the accepted scenario reference. Its initial state must be visibly qualified.

Payment party mappings and receipt/reference acceptance are preconditions supplied by the synthetic scenario. Production verification is not implemented. The 19% tax figure is an arithmetic assumption, not legal advice.

Observed inputs go in the runtime. `evaluation_only/` is for unit/integration test authors; model prompts and the company/officer app must not load its answer keys. No corpus of legal excerpts is supplied: the official sources must be selected, read and page-referenced before ingestion.

The fixture generator script is included in `scripts/generate_fixtures.py`. Run from the pack root as `python scripts/generate_fixtures.py --output-root .`; the output path is configurable and the script does not access any network.
