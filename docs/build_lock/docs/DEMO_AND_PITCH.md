# Demonstration and pitch content

## Product message

**“Boussla ne demande pas seulement si une facture est bien calculée : il aide à comprendre à quoi elle correspond et quelles pièces expliquent un écart.”**

This is a proposed message, not a novelty or superiority claim about all existing systems.

## Five-minute sequence

**0:00–0:35 — Company.** Show the synthetic-data banner. A company uploads a buyer-side invoice; a preloaded, explicitly simulated seller observation is available. State that two files from the same uploader would not provide this independent-origin evidence.

**0:35–1:15 — Context.** The invoice contains 2,000 units. The company selects a masonry work package and answers two useful questions: which allocation/reference supports the purchase and whether the quantity also serves another work package. The model routes/extracts; the user confirms the fields.

**1:15–2:10 — Officer.** Buyer/seller/payment comparisons agree, but the accepted first-work-package procurement allocation is 1,000 units. Open the exact quantity reference. Show three independent indicators: priority, evidence coverage and request status.

**2:10–2:45 — Hypotheses.** Show the baseline residual and a +10% fictional sensitivity scenario. Explain that the scenario is not an authorization and is not a probability of fraud. The open question is whether a second allocation or amendment explains the excess.

**2:45–3:35 — Clarification.** Officer approves a neutral in-app request. Company uploads an allocation for another work package. The new piece is a candidate, not an automatic clearance. The case is unchanged before officer review.

**3:35–4:20 — Revision.** Officer accepts the scope after checks. One transaction's allocation changes from 2,000/0 to 1,000/1,000. Actual recomputation resolves the first finding, preserves history and invalidates the old draft approval. Retry acceptance: nothing is duplicated.

**4:20–5:00 — Honesty and result.** Open an insufficient-evidence case and a late-but-valid response case. Show actual test counts and provider modes. A LangSmith trace demonstrates node visibility if it really exists; a local trace is explicitly local. No recovery amount or guilt claim.

## Safe clarification wording

> **Démonstration — données synthétiques — notification interne à l'application uniquement**
>
> Les pièces disponibles présentent une différence entre l'affectation de l'achat et la référence du lot indiquée dans le dossier. Merci de préciser si une partie de l'achat concerne un autre lot, un stock ou une modification du périmètre, et de joindre les éléments correspondants. Cette demande ne constitue pas une conclusion de fraude ni une décision administrative.

Numbers/references come from the scoped fact table and are inserted by code. No invented official seal, legal deadline or signature. This wording is a draft for mentor review, not an approved statutory template.

## 12-slide content outline

1. Boussla and the officer/company clarification loop.
2. One concrete problem: a correct-looking invoice can still need contextual verification.
3. Data: observed synthetic records, stated claims and public references kept separate.
4. Company input: invoice, source, purpose, project and dates.
5. Exact cross-checks: identities, amounts, settlement and allocation.
6. Bounded AI graph: extraction, questions, retrieval, draft; code controls decisions.
7. Live case: 2,000 units versus a 1,000-unit documented allocation.
8. Explanation and correction: a scoped second-project allocation changes the case.
9. Actual results: denominator, parser comparison, tests and timings.
10. Safeguards: no inverse loyalty, no automatic lateness penalty, no AI-origin guilt detector.
11. Deployment limits and proposed authorized pilot.
12. Team, code/run link, exact tools and outside-source attribution.

## Strong questions to prepare for

**Why not Excel?** Show the actual benefit on differently formatted documents and the controlled multi-user clarification workflow. If no comparison was measured, state that.

**Why would companies upload this?** The prototype demonstrates preparation/review of selected transactions or requested evidence. It does not impose nationwide compulsory reporting. Validate user burden and integration with actual authorized workflows in a pilot.

**What if both parties collude?** Matching records cannot alone prove economic reality. The app states that limitation and can request other evidence; it does not claim to solve collusion universally.

**Why is the late company not automatically punished?** The tool distinguishes communication status from the evidence for a financial finding. Actual legal action remains outside the demo.

**Is the invoice genuine?** The app shows exactly which integrity/provenance checks ran. Unknown origin remains unknown. A hash, model or human click is not universal authentication.

**How much money is saved?** Not established. Show measured task time and case correctness, or state which impact measurements have not been performed.
