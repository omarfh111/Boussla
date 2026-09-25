# Source register and verification limits

**Checked for this planning pack:** 25 September 2026. Public documentation was read; no provider account, live API call, production dataset or deployed BOUSSLA repository was tested. File references below identify supplied plans, not independent implementation evidence. Read `PACK_VALIDATION.md` separately for local reference-code/PDF checks.

## Supplied sources

**FILE-V2:** `BOUSSLA_V2_Revised_End_to_End_Plan_4_AI_Engineers(1).md`. Relevant sections: §1 enterprise-first product; §3 official requirements/provenance as cited in that plan; §6 bounded architecture; §7 source semantics; §15 internal/company scoping; §16 controlled revision. Its reported original ZIP/CSV audit was not reproduced here. Its legal-reference proposals are not treated as validated law.

**FILE-V3:** `BOUSSLA_V3_LOCKED_IDEA_AND_DATA_PLAN.md`. Retains two-stage screening/investigation, Jev routing, explicit uncertainty, scoped evidence and revision. V4 deliberately changes the entry experience into a small company intake plus officer review and reduces the large ML experiment because the user now states eight hours remain.

**User's latest requirements:** two invoice perspectives, intended-use/context questions, short/long horizon, enterprise history, hypotheses, risk/loyalty, clarification loop, provenance/AI-origin checks, Jev/Qdrant/LangGraph/LangSmith, four humans and five coding/review tool allocations. The final lock retains the workflow but explicitly replaces inverse loyalty and automatic late-upload penalties.

## Public technical sources

### WEB-JEV — official models and API

- `https://docs.typesafe.ai/models`
- `https://docs.typesafe.ai/api`

Verified documentation: Jev consumes text/structured state; the model page lists `jev-1.13.0`; the HTTP API uses `POST https://api.typesafe.ai/v1/systemone` with a bearer key, `model`, `state` and a map of typed `questions`. Choice answers select from declared categories. English is documented as its strongest language. No live request/access/latency or French evaluation was performed. The quickstart URL failed to open in this review; the models/API pages were available. Do not rely on similarly named third-party sites or send keys to them.

### WEB-JEV-LIMITS — numerical and adversarial limitations

`https://docs.typesafe.ai/model-jaggedness/jev-1.13`

The provider documents weaknesses in arithmetic, counting, date comparison, indirection and hostile state content. This supports keeping calculations and permissions in application code. It is not evidence that our prompts prevent all manipulation.

### WEB-QDRANT — local mode and semantic retrieval

- `https://qdrant.tech/documentation/frameworks/langchain/`
- `https://qdrant.tech/documentation/fastembed/fastembed-semantic-search/`
- `https://qdrant.tech/documentation/quickstart/`

Local Python mode can persist a small vector collection without a database server. This pack chooses it to reduce setup. Exact installed client APIs and concurrency behavior still need testing. If using a server, its quickstart warns that defaults are not authenticated/encrypted; do not expose it on the venue network without deliberate controls.

### WEB-EMBED — small multilingual embedding option

- `https://qdrant.github.io/fastembed/examples/Supported_Models/`
- `https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

The FastEmbed list and model card provide the starting point for a local multilingual encoder. Confirm the exact identifier in the installed package, token limit, dimension, licence and language suitability. The model is not downloaded or benchmarked by this pack. Do not choose an English-only model and silently claim Arabic coverage.

### WEB-LANGGRAPH — pauses, resume and persistence

- `https://docs.langchain.com/oss/python/langgraph/interrupts`
- `https://docs.langchain.com/oss/python/langgraph/persistence`

Documentation supports checkpointed human-input interrupts and resume. Interrupted nodes can rerun from their beginning. BOUSSLA's role checks, transaction semantics, idempotency and audience scoping remain our application design and are not supplied automatically by LangGraph.

### WEB-LANGSMITH — sensitive tracing data

`https://docs.langchain.com/langsmith/mask-inputs-outputs`

Documents `LANGSMITH_HIDE_INPUTS` and `LANGSMITH_HIDE_OUTPUTS`, client/processors and additional redaction. This pack also requires metadata/error review. No LangSmith project or successful remote trace was created in this review. Quotas and billing need account confirmation.

### WEB-C2PA — provenance versus truth

`https://spec.c2pa.org/specifications/specifications/2.2/explainer/Explainer.html`

This is the specifically consulted explanatory version, not a claim it is the latest specification. Its provenance FAQ says provenance does not establish that content is true/accurate and that absence of Content Credentials does not automatically make an asset untrustworthy. Creation/edit provenance and economic-event validity remain different checks.

### WEB-C2PA-SDK — open-source Python tools

- `https://github.com/contentauth/c2pa-python`
- `https://github.com/contentauth/c2pa-python/blob/main/docs/context-settings.md`

The official Content Authenticity Initiative Python repository describes reading/validating manifests, supported formats and configured trust. Source licences are Apache-2.0/MIT. Runtime/format behavior and trust anchors need actual tests. Disable unsolicited remote-manifest fetching in the local demo; do not equate a manifest's existence with cryptographic validation or truthful content.

### WEB-PYHANKO — PDF signature validation

- `https://docs.pyhanko.eu/en/latest/cli-guide/validation.html`
- `https://docs.pyhanko.eu/en/latest/lib-guide/validation/general-api.html`

Signature validation uses a configured validation/trust context. Missing revocation/trust information can prevent a conclusive result. The actual transaction and issuing authority are not proved by successful byte-signature validation. Do not download broad external trust lists during the eight-hour critical path.

### WEB-DOCTAMPER — research limitations and dataset access

`https://github.com/qcf-568/DocTamper`

The authors' repository describes document-text tampering research. It states the original dataset does not cover AIGC text tampering and describes a restricted non-commercial research application process. That does not justify dropping a generic ready-to-use invoice-authenticity detector into the MVP. Neither weights nor data were downloaded/evaluated here.

### WEB-NIST — general transparency research context

`https://www.nist.gov/publications/reducing-risks-posed-synthetic-content-overview-technical-approaches-digital-content`

Publication landing page for NIST AI 100-4, *Reducing Risks Posed by Synthetic Content*. The landing-page abstract covers provenance, labelling, detection and testing. It is context, not an invoice benchmark or a claim that this review inspected every page of the report. No specific performance number is taken from it.

## Runtime accounts are not coding-tool subscriptions

### WEB-OPENAI-BILLING

- `https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan`
- `https://help.openai.com/en/articles/9039756`

Codex can be accessed under supported ChatGPT plans; standard OpenAI API billing is separate. Confirm the team's actual runtime API key and budget. Do not infer an inference endpoint from a Codex login or improvise shared credential workarounds.

### WEB-CLAUDE-BILLING

- `https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan`
- `https://support.claude.com/en/articles/9876003-i-have-a-paid-claude-subscription-pro-max-team-or-enterprise-plans-why-do-i-have-to-pay-separately-to-use-the-claude-api-and-console`
- `https://support.claude.com/en/articles/15036540-use-claude-agent-sdk-with-your-claude-plan`

Distinguish interactive Claude Code subscription usage, standard Claude API/Console billing and any separately claimable Agent SDK credit. The current support page describes a possible Agent SDK credit for eligible plans; this review did not inspect the team's account or eligibility. Do not assume unlimited application inference or that the credit applies to ordinary API-key calls.

### WEB-GEMINI-BILLING

- `https://ai.google.dev/gemini-api/docs/billing`
- `https://ai.google.dev/gemini-api/docs/pricing`

Check the API project's actual key, model availability, free/paid tier, rate limits and data-use conditions. The team's Gemini app subscription is not evidence that every requested runtime API call is authorized, free or available. No API usage was executed here.

## Public fiscal references

### WEB-JIBAYA

`https://jibaya.tn/docs/`

The official catalogue lists fiscal-code editions and notes. The catalogue was opened. This is not an audit of the whole law corpus, not a dataset of declarations and not authorization for any specific notice or response deadline.

### WEB-FINANCE

`https://www.finances.gov.tn/fr/node/2809`

The Ministry's Finance Law 2026 page was opened. The team's local PDF was not supplied for byte comparison in this turn. Ingest the correct edition and relevant passages only after verification. This source does not specify the quantity of bricks needed for a construction project.

## Gaps that remain

Real source access, legal basis for the company workflow, whether compulsory evidence collection is appropriate, the actual registered secondary challenge, interpretation of individual fiscal rules, runtime keys/limits, final installed versions, model accuracy, latency and real-world effect all remain to be established by the team and appropriate reviewers.
