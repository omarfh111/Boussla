# Data to use and how to obtain it

## 1. Exact data classes

**A. Synthetic transactional data** — main runtime source. Create enterprises, supplier observations, invoice lines, settlements, project context, quantity references and case history. These are invented examples, not extracted taxpayer records.

**B. Selected official public references** — a small legal/context corpus from JIBAYA and the Ministry, with exact pages/versions. It supports reference retrieval, not proof that a specific company violated a rule. Check permitted use. [WEB-JIBAYA, WEB-FINANCE]

**C. Company-uploaded documents and reasons** — untrusted attributed assertions until the relevant verification/review steps. A field confirmed by the company means confirmed transcription, not independently authenticated.

**D. Evaluation truth** — separate answer keys. Runtime services, model prompts and Qdrant never read them.

No raw dataset of the team's other research is assumed available. The older INS audit counts are claims reported by the uploaded plan, not a new audit here. INS annual aggregates are unnecessary for the eight-hour core.

## 2. Minimum proposed tables

| File/table | Grain and purpose |
|---|---|
| `entreprises` | One synthetic entity |
| `transactions` | One economic sale/purchase, independent of duplicate observations |
| `invoice_observations` | One source's view of one invoice/version |
| `invoice_lines` | One line/item under an observation |
| `payments` | One documented settlement observation |
| `payment_allocations` | Amount assigned from one payment to one transaction |
| `projects` | One named project or business-use scope |
| `context_claims` | Versioned reason, beneficiary, horizon and author |
| `quantity_references` | One scoped item/unit/date reference with provenance and kind |
| `allocations` | One accepted/proposed quantity assignment or transfer |
| `source_coverage` | One company/source/window with applicability and availability |
| `documents` | Immutable original file and origin metadata |
| `dm` | Optional imported/simulated monthly tax summary, with no double counting |
| `findings`, `hypotheses`, `score_snapshots` | Versioned derived results |
| `clarification_requests`, `responses`, `case_revisions`, `action_receipts` | Workflow and idempotency |

TEJ, CNSS, DAU and liasse retain their old meaning if a working adapter exists. Do not rename a bank-like payment CSV to TEJ. Do not pretend the current pack provides a live feed or official schema implementation.

## 3. Size target and a cut rule

First integration: six showcase cases and 12–20 documents. Then about **50 companies, 12 completed months, 500–1,000 linked synthetic transactions** if the core is stable. Those are targets, not data already generated in this pack. The included CSVs/PDFs are deliberately much smaller, explained below.

The older 32-month/5,000-enterprise target is deferred unless already working. Large scale is not needed to demonstrate matching, contextual reasoning or correction. Do not generate a PDF for every history row.

## 4. The showcase cases

| Case | Observation | Correct behavior |
|---|---|---|
| BRICKS-ALLOCATION | Buyer/seller/payment agree, but 2,000 units are assigned to a work package with a 1,000-unit accepted procurement allocation | Flag the scoped allocation difference; propose questions; resolve only on accepted budget-valid second-project allocation |
| COUNTERPARTY-CONFLICT | Same transaction identifier but buyer copy differs materially from a preloaded seller observation | Show the exact conflicting field and origin; do not choose one silently |
| PART-PAYMENT | Invoice amount exceeds a documented installment paid before the remaining due date | Recognize terms or abstain; no automatic settlement discrepancy |
| SAME-ORIGIN | Company uploads both apparently matching copies | Matched documents, independence not established; no authenticity claim |
| MISSING-SUPPLIER | No counterpart source yet available | Pending corroboration, not “supplier fraud” |
| LATE-VALID-RESPONSE | Correct supporting allocation arrives after the demo target | Mark response received, evaluate evidence normally; risk is not increased by timing alone |

Vehicle case is P2: one company-funded asset with conflicting ownership/accounting documentation. Personal use alone is not labelled fraudulent. Its separate legal treatment requires mentor/source validation. No risk propagation from one owner's name or lifestyle.

## 5. Files included here

`fixtures/documents/` contains fictional native-text PDFs for a buyer invoice, a separately supplied seller-view fixture, payment record, procurement allocation, delivery record, candidate second-project allocation, a conflicting invoice view and a prompt-injection stress document. They have prominent synthetic-demo labels and no official logos, seals, credentials or actual banking details.

`fixtures/observed/` contains small JSON/CSV records for those examples. This is one complete document-backed development fixture, not a representative dataset or held-out benchmark. The other showcase cases are described as test variations to implement, not already functioning workflows. `fixtures/evaluation_only/` contains expected outcomes for tests. The app must not load this directory.

PDF generation and quality checks are described in `PACK_VALIDATION.md`. These PDFs are text-template generated, not statistical AI-authenticity benchmarks.

## 6. Independent evaluation set to create during development

B and the shared Gemini reviewer should define approximately 20–30 additional cases, group repeated versions/layout variants together and keep them separate from prompt tuning. Use neutral IDs. Include legitimate lookalikes, unknown sources, out-of-scope comparisons and corrections to only part of an allocation.

The oracle is an explicit fixture rule plus known source data. Record what requires mentor review. Do not let the extractor generate its own labels or grade itself.

For document extraction, compare the AI path with a deterministic parser on the same PDFs. Report raw field accuracy and final accepted-result correctness separately. Abstention is not extraction success, but may be the correct safe workflow outcome.

## 7. Qdrant ingestion

Ingest only a curated public corpus for P0. Each record needs exact excerpt, URL, source date/hash, page/article, jurisdiction, effective date bounds, language, semantic topic and `review_status`.

Include 10–30 relevant passages only after reading them. Do not auto-download a national legal corpus. Do not turn a source filename into a verified legal reference. The local `law of finance 2026.pdf` mentioned earlier must be compared against the official edition before asserting identity.

Never put fictional legal rules into the real-law collection. Synthetic procurement limits belong to case evidence or `demo_policy`, visibly separate. A public law text does not establish how many bricks are needed to build a specific house.

## 8. Financial history semantics

Display three separate monthly panels: invoiced sales/purchases, observed settled inflows/outflows and supplied declared totals. Provide time-window and coverage labels. Loans, equity, transfers, refunds, credit notes and tax withholding are not silently treated as sales/purchases. A company history describes only the available sources, not all of its economic activity.

Generate underlying business events first, then source views with controlled timing/coverage. If a copy differs, preserve both observations and label which data-generating mechanism is hidden from runtime. Do not create unrelated random numbers across sources and call every difference misconduct.
