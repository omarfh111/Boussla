# Public-reference candidates for the officer dossier

The eight records in `public_references.json` are exact short passages inspected on
2026-09-26 from the [Tunisian Ministry of Finance invoice and transport FAQ](https://www.finances.gov.tn/fr/node/952).
The SHA-256 of the inspected HTML response was
`9fbdad1650772ef219382159665ab51c286c15fab60ed3a16d681d5cb350885e`.
`REVIEWED` means the stored text was checked against that source; it does not
mean that legal applicability was reviewed. The page gives no publication or
effective date for these excerpts, so those fields are null. No article or page
number was assigned to this HTML page.

The only backend is local lexical matching (`backend_mode="LEXICAL"`, result
`mode=TEMPLATE`). Qdrant and embeddings are `NOT_RUN`. A missing or empty
corpus returns no passages. The source hash can be rechecked against a fresh
download; a changed page must be reinspected before updating the corpus.

Lane A wiring at the officer view boundary:

```python
from boussla.retrieval.corpus import public_reference_retriever
from boussla.retrieval.queries import candidate_passages_for_reasons

retriever = public_reference_retriever()  # cache once in the service process
passages = candidate_passages_for_reasons(
    retriever,
    ((f.family, f.reason_code) for f in officer_findings),
    as_of=case_cutoff_date,
)
# Set OfficerCaseView.candidate_passages=passages; keep score inputs unchanged.
```

Only four allowlisted counterparty reason codes produce fixed queries. No raw
invoice text, tax ID, company name or user prose enters retrieval. Show results
under the label **« passages de référence candidats à examiner »**. The officer
must verify the source, version, date and applicability before citing a passage.
Do not show them as an automatic legal conclusion or add them to the review
index. Because effective dates are unknown, the company audience receives no
passages from this corpus.

`RetrievedPassage` currently carries the source URL, title, text and review
status but not the stored source hash or source/effective dates. If these must
be displayed, Lane A should extend that shared contract and its renderer; the
corpus retains all of those fields.
