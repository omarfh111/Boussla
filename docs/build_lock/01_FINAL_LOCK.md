# BOUSSLA Context — Final eight-hour scope

**Version:** 4.0. **Planning date:** 25 September 2026. **Team:** four people. **Implementation window:** eight hours maximum, bounded by the actual official freeze.

> **BOUSSLA connects an invoice, its counterparty record, observed settlement and stated business purpose; tests documented explanations; and gives an officer an evidence-backed review queue with a controlled clarification loop.**

French pitch:

> **Boussla rapproche les pièces, les paiements observés et le contexte déclaré d'une opération. Il explique les écarts, propose les justificatifs utiles et aide l'agent à réviser le dossier quand de nouvelles pièces arrivent.**

No concept can assure a win. The proposal as originally phrased contains weaknesses that must be corrected. The locked version aims for a complete, inspectable demonstration rather than universal fraud detection.

## 1. What changes from previous BOUSSLA versions

The supplied V2/V3 plans centered enterprise prioritization, source crossing and controlled case review. V3 excluded a company portal from its initial release. This proposal explicitly changes that: add **a small company evidence form and response inbox in the same application**, not a second standalone SaaS product.

Retain T20 as the principal project mapping and the existing optional T4 designation, pending mentor confirmation. An evidence checklist is not by itself a demonstration of official trusted-operator facilitation. Do not silently change the registration or add T6/T7/T9 as extra selected challenges.

With eight hours, replace the mandatory 5,000-company ML experiment with a transparent, versioned review-priority baseline and measured document/workflow tests. Preserve any already working tax-source/LightGBM module as a separately labelled view; do not blend its score with new transaction findings without a new model and evaluation.

## 2. The five essential corrections

### 2.1 One transaction, two perspectives—not two independent invoices by assumption

A seller's issued invoice and the buyer's received copy generally describe the same sale. The buyer's own purchase ledger entry is another observation, not a second invoice that creates another expense. Require one primary invoice plus an available corroborating document/record, or an explicit “not available” status.

The stronger counterpart is an independently supplied seller record. If one company uploads both files, record the common source. Renaming the second file “supplier invoice” does not make it independent. An independent fixture is labelled simulated counterpart provenance, not a live supplier connection.

Compare issuer/buyer identifiers, invoice reference/version, date, currency, net/tax/gross and normalized line quantities. Image similarity is not the main reconciliation criterion.

### 2.2 Separate invoiced, paid and declared amounts

An invoice is a claim for payment, not evidence of cash settlement. Show invoiced purchases/sales, observed settled cash movements and declared totals in separate views. Link explicit payment allocations to invoices; support partial payments and known adjustments or return “not comparable.”

A tax identifier printed on a PDF establishes what the PDF says, not ownership of a bank account. A payer/payee mapping needs its own supplied provenance.

### 2.3 Purpose and time are context, not proof

Ask “For which project?”, “Who benefits?”, “What is the planned use period?”, “Which phase?”, “Is this purchase for stock, immediate use or a longer-lived asset?”, and “Which reference supports the planned quantity?”

Store the answers as **company-declared claims**. Do not infer a construction estimate from “a house.” Do not classify long duration as safe or short duration as suspicious. Ask project-level questions once and reuse the project record; do not impose repeated free-form justification for every ordinary purchase.

### 2.4 Replace loyalty with three separate indicators

1. **Review-priority index:** supported unresolved discrepancies within the implemented checks; not probability of fraud.
2. **Evidence coverage:** which applicable checks can actually be performed; not a moral or loyalty score.
3. **Clarification status:** pending, answered, extension requested, overdue for follow-up, or closed.

No `loyalty = 100 - risk`. A complete dossier can have high risk; a low-risk dossier can be incomplete. No drastic automatic penalty for delay. Deadline-based follow-up requires a valid request, delivery/availability information and allowance for extensions or service outages. For the prototype, dates are explicit demo targets, not legal deadlines.

### 2.5 Replace “AI-generated = fake” with document-integrity inspection

Keep separate: byte integrity, available provenance/signatures, document content consistency and economic-event support. An AI-assisted invoice can represent a real sale; a manually produced invoice can be fictitious. Absence of a signature or Content Credentials is neutral. A signed false statement can still be false. [WEB-C2PA, WEB-PYHANKO]

## 3. The one workflow to finish

```text
Company uploads invoice + available corroboration
   -> confirms extracted fields
   -> identifies purpose/project and dates
   -> app links known history and counterpart observations
   -> deterministic invoice/payment checks
   -> contextual questions + bounded scenario tests
   -> enterprise review index with specific causes and coverage
   -> officer inspects evidence/hypotheses
   -> officer publishes a neutral in-app clarification request
   -> company uploads a response/new piece
   -> officer accepts or rejects its scoped use
   -> new case revision, recalculated finding and updated dossier
```

Same underlying case, two permission-scoped views. No closure, penalty, payment, official status or real message is executed. The company view sees its own transactions and permitted questions, not other enterprises' compliance or internal ranking.

## 4. The primary scenario

**Supported domain:** purchase allocation for one building-material work package, not engineering design of a bridge.

A fictional company buys 2,000 units for a named masonry work package. Buyer and independently preloaded seller records agree. Observed payment allocation also agrees. A supplied procurement-allocation record permits 1,000 units for the selected work package at the chosen date. A discrepancy remains about allocation—not arithmetic.

The model proposes possible explanations: a second work package, authorized stock, an amendment, or a record mismatch. Code evaluates only hypotheses with the right supplied evidence. A free-text claim does not clear the finding.

The company responds with a **1,000-unit allocation to a second authorized work package**, tied to the same purchase. On officer acceptance and quantity-budget checks, the system revises the original allocation: 1,000 units for the first package and 1,000 for the second. The original finding resolves in that scenario. No units may be allocated twice.

Important: buying stock for future use can be legitimate. The above bound is a specific fixture's procurement allocation, not a universal rule that purchases must equal consumption. For a consumption estimate alone, show a planning question, not a score-producing breach. Stock does not automatically justify charging a public customer quantities beyond a contract.

## 5. Simulations are sensitivity analyses, not fraud probabilities

Run a small reproducible scenario grid, such as a base allocation and a +10% sensitivity envelope **explicitly labelled a fictional assumption**. Display residual units under each assumption and the evidence still required. Do not generate realistic-looking fake documents to serve as reference evidence. Do not interpret how often an LLM says “fraud” as a probability.

Only accepted, properly scoped evidence changes the canonical case. A hypothetical allowance never silently becomes an accepted procurement variation. Timeline sensitivity changes scenario outputs, not statutory deadlines or observed payment dates.

## 6. Locked technology stack

**UI:** Streamlit + Plotly, one modular Python app. Two role-scoped views. Preserve a working equivalent if one already exists; no forced frontend rewrite.

**Authoritative store:** SQLite for cases, immutable observations, proposals, requests, revisions and action receipts. All writes through the service layer. Money in integer millimes; quantities as decimal strings. No required database server.

**Optional history analytics:** DuckDB/Parquet only if the existing module works; not a second writable source of truth.

**Orchestration:** LangGraph with durable local checkpoints. Fixed DAG and bounded revisits, no self-directed agent swarm. [WEB-LANGGRAPH]

**Classification:** Jev through the official TypeSafe endpoint for document type/purpose routing. It is text-only; arithmetic and dates stay in code. Actual French accuracy/access remain to be tested. [WEB-JEV, WEB-JEV-LIMITS]

**Extraction/drafting:** one configured general model provider. Native PDF text first, bounded extraction into typed fields with exact source spans. Manual validated entry if parsing or the API fails.

**Retrieval:** Qdrant local mode for a small collection of legal/reference passages. A local multilingual embedding model after a download smoke test. Financial totals and tax IDs are SQL joins, not vector search. [WEB-QDRANT, WEB-EMBED]

**Tracing:** LangSmith with hidden raw inputs/outputs and whitelisted metadata; local JSON event logs remain the authoritative audit trail. Cloud tracing failure must not block the case. [WEB-LANGSMITH]

**Provenance:** SHA-256, immutable originals, metadata inventory and semantic corroboration in P0. Optional pyHanko signature validation and C2PA manifest inspection, clearly reporting unsupported/absent/unknown. No classifier-based automatic invoice rejection. [WEB-PYHANKO, WEB-C2PA-SDK]

**Testing:** Python unit tests plus integrated click-through tests. No training/fine-tuning requirement.

## 7. The executable scope boundary

P0: one material family, exact invoice match, supported payment allocation, purpose/project form, explicit unknown states, bounded hypotheses, baseline score, officer request, company reply, revision and recomputation. One native-text document layout family with variations.

P1 targeted: working Jev route, working local Qdrant retrieval, LangGraph trace, redacted LangSmith trace. These integrations are assigned tasks, but a failure must degrade honestly instead of blocking the business flow. At least one real extraction/model path must be tested before claiming an AI demonstration.

P2: vehicle case, scanned-document OCR, voice, graph analytics, learned enterprise model, C2PA/signature rich UI. Add only after P0/P1 acceptance and within the feature freeze. No mandatory bridge model or eight-scheme suite.

## 8. Intended impact and measurement

Measure correct mismatch detection, wrong-entity rejection, question relevance, source accuracy, end-to-end dossier correctness, provider latency and time to resolve a controlled case. Report numerator, denominator and mode. A workflow fixture is not a real fraud label. Do not translate a material quantity gap into tax recovered.

The strongest demonstration is that **the same system detects a supported discrepancy, exposes a legitimate explanation and revises the dossier without hiding its history**. This is an engineering thesis, not a competition outcome prediction.

## 9. Before real deployment

Validate legal basis, user roles, supplier onboarding, data-access permissions, identity proofing, retention, security, tax/accounting semantics, response rights and real-world evaluation. The hackathon cannot impose new reporting duties on every company. Public-source rule retrieval is not approval of the proposed workflow.

Detailed implementation: `contracts/CONTRACTS.md`, `docs/ARCHITECTURE.md`, `docs/SCORING_AND_SCENARIOS.md` and the five handoffs.
