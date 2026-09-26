# Public-reference candidates for the officer dossier

The eight records in `public_references.json` are exact short passages inspected on
2026-09-26 from the [Tunisian Ministry of Finance invoice and transport FAQ](https://www.finances.gov.tn/fr/node/952).
The SHA-256 of the inspected HTML response was
`9fbdad1650772ef219382159665ab51c286c15fab60ed3a16d681d5cb350885e`.
`REVIEWED` means the stored text was checked against that source; it does not
mean that legal applicability was reviewed. The page gives no publication or
effective date for these excerpts, so those fields are null. No article or page
number was assigned to this HTML page.

`public_reference_retriever()` uses `QDRANT_URL`, `QDRANT_API_KEY` and
`QDRANT_COLLECTION` from the environment. With a healthy HTTPS Cloud cluster,
it caches one Qdrant client and one local FastEmbed model per process. The model
is `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensions);
its cache is under ignored `runtime/fastembed/`. Only the eight public passages,
their metadata and locally generated vectors are sent to Cloud. The four
allowlisted finding queries are embedded locally; Cloud receives query vectors.

The dedicated collection is created if absent. An existing collection must
already contain exactly these eight IDs and exact payloads; other contents
cause lexical fallback instead of being overwritten. `backend_mode="QDRANT"`
returns `mode=LIVE`. Cloud/model failure switches to `backend_mode="LEXICAL"`
and `mode=TEMPLATE`, with a sanitized failure type. Missing corpus yields
`backend_mode="NOT_SUPPLIED"` and no passages. The source hash can be rechecked
against a fresh download; a changed page must be reinspected before updating
the corpus. The live smoke is `python -m scripts.smoke_qdrant_references` after
the three environment variables have been loaded; it prints only host, IDs,
counts and modes.

Lane A wiring at the officer view boundary:

```python
from boussla.retrieval.corpus import public_reference_retriever
from boussla.retrieval.queries import enrich_officer_view

retriever = public_reference_retriever()  # cache once in the service process
officer_view = enrich_officer_view(officer_view, retriever, as_of=case_cutoff_date)
# The helper calls candidate_passages_for_reasons(retriever,
#   ((f.family, f.reason_code) for f in officer_view.findings), ...), then sets
# OfficerCaseView.candidate_passages and mode_by_node["retrieval"].
```

Only four allowlisted counterparty reason codes produce fixed queries. No raw
invoice text, tax ID, company name or user prose enters retrieval. Show results
under the label **« passages de référence candidats à examiner »**. The officer
must verify the source, version, date and applicability before citing a passage.
Do not show them as an automatic legal conclusion or add them to the review
index. Because effective dates are unknown, the company audience receives no
passages from this corpus. Lane A must place retrieval after deterministic
checks in the officer view path. `enrich_officer_view` maps the final backend
mode to `LIVE`, `TEMPLATE` or `NOT_RUN` (a query failure may switch Qdrant to
lexical) while leaving findings and score unchanged. The existing Streamlit
officer dossier renders `candidate_passages`; Lane D should use the full label
above in that view.

`RetrievedPassage` currently carries the source URL, title, text and review
status but not the stored source hash or source/effective dates. If these must
be displayed, Lane A should extend that shared contract and its renderer; the
corpus retains all of those fields.
