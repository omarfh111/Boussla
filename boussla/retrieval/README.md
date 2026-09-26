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

`ReferenceAssistant.for_findings(findings, as_of=trusted_case_date,
audience=Audience.OFFICER)` is the narrow C-owned RAG entry point. It strips
findings to allowlisted `(family, reason_code)` pairs, retrieves at most five
official candidate passages, then optionally uses the existing configured
OpenAI general model to draft a citation-checked note. The model receives only
those pairs and public passage IDs/text. Every generated observation has a
retrieved rule ID; invented citations, definitive applicability wording,
provider errors and absent passages yield no note while passages remain. The
assistant never accepts or returns a score, finding update or evidence decision.

For Lane A, after deterministic scoring and officer view construction:

```python
from boussla.retrieval.grounded_rag import public_reference_assistant

result = public_reference_assistant().for_findings(
    officer_view.findings, as_of=trusted_case_date, audience=Audience.OFFICER,
)
officer_view = officer_view.model_copy(update={
    "candidate_passages": result.candidate_passages,
    "mode_by_node": {**officer_view.mode_by_node, "retrieval": result.retrieval_mode},
})
# Keep result.grounded_note in an officer-only rendering path; the shared
# OfficerCaseView contract currently has no note field. Lane A owns any contract
# extension or service wiring. Do not put this note in company views.
```

Lane D/A display contract: **« Passages de référence candidats à examiner »**,
then optionally **« Synthèse assistée à partir des passages retrouvés »** with
visible `result.cited_rule_ids` and **« Synthèse indicative — l'applicabilité
doit être vérifiée par l'agent. »**. The candidate list and optional note are
never an automatic legal opinion. The fixed synthetic retrieval evaluation is
`python -m scripts.evaluate_reference_retrieval`; its top-1/top-3 numbers
measure retrieval on those queries only, not legal accuracy.
