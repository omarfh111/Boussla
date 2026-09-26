# Officer reference candidates

`public_references.json` contains 29 inspected short passages from four official
Tunisian documents: two Ministry of Finance FAQ pages, the JIBAYA 2023 VAT-code
compilation, and JIBAYA Note commune 11/2009. Every record contains the SHA-256
of the inspected HTML/PDF response, URL, title, printed PDF page where applicable,
and an exact short excerpt. The PDF publication dates were not independently
established, so `source_date` is null; the VAT compilation's title identifies its
2023 update, and the Note identifies 2009. Effective dates remain null. `REVIEWED`
means the excerpt was inspected against its cited source, not that current legal
applicability was established. The officer must check the current source and law.

The manifest is bounded at 50 records. The Qdrant backend requires 8–50 unique,
reviewed, official Tunisian references and uses only their public text/metadata.
The default collection is `boussla_public_references_v2`. Set `QDRANT_COLLECTION`
to this name when loading credentials from an older `.env`; the original
`boussla_public_references` collection is left untouched. An existing collection
must match the manifest's deterministic IDs and every payload exactly; extra,
missing or changed points cause labelled lexical fallback, never destructive
replacement. Only an empty/new collection is ingested.

`public_reference_retriever()` uses `QDRANT_URL`, `QDRANT_API_KEY`, and
`QDRANT_COLLECTION`. FastEmbed runs locally with
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions)
and caches under ignored `runtime/fastembed/`. Cloud receives the public vectors,
payloads, and bounded query vectors. Healthy Cloud results have `mode=LIVE` and
`backend_mode=QDRANT`; unavailable Cloud/model gives `mode=TEMPLATE` and
`backend_mode=LEXICAL`; absent corpus gives `NOT_SUPPLIED` and no passages.
Unknown effective dates suppress all company-audience passages.

Lane A may call `candidate_passages_for_reasons(retriever,
((f.family, f.reason_code) for f in findings), as_of=trusted_case_date)` after
deterministic scoring, then populate `OfficerCaseView.candidate_passages` and
`mode_by_node["retrieval"]`. `enrich_officer_view` already demonstrates this
without altering findings or review index. Only allowlisted reason codes produce
queries. No invoice text, tax ID, company name, payment data, or arbitrary user
text enters retrieval. Display under **« Passages de référence candidats à examiner »**;
these are candidates, not automatic legal conclusions.
