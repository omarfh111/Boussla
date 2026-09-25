# Document-integrity and AI-origin inspection

## Objective

Inspect what the supplied file and corroborating records support. Do not claim that a free model can reliably decide whether every invoice is AI-generated, genuine, fraudulent or legally valid.

Creation method, file integrity, issuing identity, transaction existence and tax treatment are different questions. A template created with AI can describe a real transaction. A paper invoice can describe a nonexistent one.

## Required P0 layers

**1. Safe ingestion.** Preserve original bytes and compute SHA-256. Limit file bytes/pages/decoded pixels, validate MIME/header rather than extension alone, use random server-side storage names, never execute scripts/macros or follow embedded links. Reject encrypted or unsupported files. Any rendering/extraction subprocess has a timeout and no arbitrary network access. Escape extracted text in the UI.

**2. Structural inventory.** Extract native text, page count, basic PDF producer/creation metadata and signature presence where possible. Report observations only. A modern PDF editor, new creation date, odd font or lack of metadata is not proof of tampering. Do not use error-level analysis or “looks AI-generated” as a verdict.

**3. Semantic consistency.** Check issuer/buyer identifiers, invoice reference, totals, line units/quantities, linked payment and scope. An extraction conflict is first a document review issue, not automatically a financial discrepancy.

**4. Provenance and corroboration.** Record who actually supplied each observation. Two files supplied by the same company cannot authenticate one another. Even independently agreeing seller/buyer documents can be false or collusive; independently sourced evidence is stronger for a claim but not proof of physical delivery.

## Optional open-source layers

| Tool | Useful for | Does not establish | Budget |
|---|---|---|---|
| `pyHanko` | Validation of an embedded PDF signature against a specified trust context | That the sale occurred, or that a signer is legally authorized for this company | Optional 20-minute integration gate |
| `c2pa-python` | Reading/validating available Content Credentials on supported formats; inspecting declared creation/edit provenance | Truth of invoice content or universal detection of AI generation | Optional after P0, with exact format/version test |
| `pypdf` and standard `hashlib` | Native text/metadata, byte hashes, deterministic inspection | Authenticity or a forgery verdict | P0 |
| DocTamper research | A possible later experiment on manipulated document text | A validated detector for your invoices or generic AI-generated invoices | Do not integrate tonight |

The DocTamper repository states that its original dataset does not cover AIGC text tampering and describes restricted non-commercial research access/application requirements. It is not a frictionless public invoice-fraud dataset. [WEB-DOCTAMPER]

No suitable universal free “AI invoice authenticity API” was established in this review. Do not send confidential invoices to random detector sites. Use only synthetic inputs with any external provider in the prototype.

## Status object

```json
{
  "file_integrity": "HASH_RECORDED",
  "pdf_signature": "NOT_CHECKED",
  "signature_trust": "UNKNOWN",
  "c2pa": "NOT_CHECKED",
  "ai_origin": "UNKNOWN",
  "issuer_corroboration": "COMPANY_SUPPLIED_ONLY",
  "semantic_checks": "PENDING",
  "limitations": ["A file hash does not establish authenticity."]
}
```

Distinguish ABSENT, UNSUPPORTED, INVALID, VALID_IN_CONFIGURED_TRUST_CONTEXT and NOT_CHECKED. “Signature present” is not “signature valid.” Test-certificate trust is labelled demo trust, not government certification. Disable remote manifest/AIA/OCSP retrieval unless explicitly approved and safely configured; otherwise report trust/revocation as unknown. Inspect tool defaults. [WEB-C2PA-SDK, WEB-PYHANKO]

If a verified provenance claim declares AI generation, report that narrow claim. Do not infer that the transaction is fictitious. If credentials are absent, origin stays unknown; it is not “human-generated.” C2PA explicitly distinguishes provenance from truth and does not prescribe distrusting all unsigned media. [WEB-C2PA]

## Required adversarial examples

A legitimate machine-generated invoice; a manually altered amount; identical invoice copies; differently rendered legitimate copies; signature absent; signature present but unvalidated; wrong-company evidence; a prompt injection in the footer; a benign late upload; a mismatched currency; an unsupported scan.

Creation origin must not be perfectly correlated with anomaly labels in the fixtures. Never claim a generic visual detector has been validated using only easy generated images and clean scanned originals.

## Exclusions

No new deepfake/forgery detector training, no mandatory GPU, no claim that OCR or Jev authenticates a document, no automated adverse action from a detector score. Metadata/provenance issues go to a separate document-review lane, not silently into the financial-risk score.
