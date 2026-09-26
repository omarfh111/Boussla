# Fixed synthetic retrieval evaluation

Run on 2026-09-26 against `boussla_public_references_v2` (29 verified public points).
Local FastEmbed model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions.
All 21 queries used Qdrant Cloud `LIVE` mode. Top-1: **16/21**; top-3: **19/21**.
These are retrieval hit metrics against predefined acceptable IDs, not legal-accuracy or fraud metrics.

| Case | Top-1 | Top-3 | Returned rule IDs (rank order) | Mode |
|---|---:|---:|---|---|
| reason_fields | 1 | 1 | TN-NC11-09-SELLER, TN-MOF-FAQ-952-INVOICE-NUMBER, TN-NC11-09-CLIENT | LIVE |
| reason_amount | 1 | 1 | TN-MOF-FAQ-952-VAT-RATE, TN-TVA23-18-TAX, TN-TVA23-18-SUSPENSION | LIVE |
| reason_identity | 1 | 1 | TN-NC11-09-GOODS-PRICE, TN-TVA23-18-GOODS-PRICE, TN-MOF-FAQ-952-ITEM-PRICE | LIVE |
| reason_line_amount | 1 | 1 | TN-MOF-FAQ-75-GOODS-PRICE, TN-MOF-FAQ-952-ITEM-PRICE, TN-MOF-FAQ-952-VAT-RATE | LIVE |
| date_operation | 1 | 1 | TN-MOF-FAQ-952-OPERATION-DATE, TN-NC11-09-DATE, TN-TVA23-18-DATE | LIVE |
| buyer_identification | 1 | 1 | TN-NC11-09-CLIENT, TN-MOF-FAQ-952-CLIENT, TN-NC11-09-SELLER | LIVE |
| buyer_tax_number | 1 | 1 | TN-MOF-FAQ-75-BUYER-CONDITION, TN-NC11-09-SELLER, TN-TVA23-18-TAX | LIVE |
| seller_tax_number | 0 | 1 | TN-MOF-FAQ-952-INVOICE-ISSUE, TN-NC11-09-SELLER, TN-MOF-FAQ-952-VAT-RATE | LIVE |
| continuous_numbering | 1 | 1 | TN-NC11-09-NUMBERING, TN-MOF-FAQ-952-INVOICE-NUMBER, TN-MOF-FAQ-75-NUMBERING | LIVE |
| transport_record | 1 | 1 | TN-MOF-FAQ-952-TRANSPORT, TN-MOF-FAQ-75-TRANSPORT, TN-MOF-FAQ-952-ITEM-PRICE | LIVE |
| goods_description | 0 | 0 | TN-MOF-FAQ-75-TRANSPORT, TN-MOF-FAQ-952-TRANSPORT, TN-MOF-FAQ-952-INVOICE-ISSUE | LIVE |
| price_before_tax | 0 | 0 | TN-MOF-FAQ-952-VAT-RATE, TN-TVA23-18-TAX, TN-TVA23-18-SUSPENSION | LIVE |
| vat_amount | 1 | 1 | TN-MOF-FAQ-75-TAX, TN-MOF-FAQ-75-GOODS-PRICE, TN-MOF-FAQ-75-BUYER-CONDITION | LIVE |
| vat_suspension | 1 | 1 | TN-TVA23-18-SUSPENSION, TN-TVA23-18-ELECTRONIC, TN-TVA23-18-INVOICE-DUTY | LIVE |
| non_vat_exception | 0 | 1 | TN-MOF-FAQ-75-TAX, TN-NC11-09-NON-VAT, TN-MOF-FAQ-75-GOODS-PRICE | LIVE |
| electronic_invoice | 1 | 1 | TN-TVA23-18-ELECTRONIC, TN-NC11-09-REQUIRED-MENTIONS, TN-MOF-FAQ-952-TRANSPORT | LIVE |
| invoice_obligation | 1 | 1 | TN-MOF-FAQ-952-INVOICE-ISSUE, TN-TVA23-18-INVOICE-DUTY, TN-MOF-FAQ-75-TRANSPORT | LIVE |
| delivery_slip | 0 | 1 | TN-NC11-09-GOODS-PRICE, TN-MOF-FAQ-952-TRANSPORT, TN-MOF-FAQ-75-TRANSPORT | LIVE |
| series_no_gap | 1 | 1 | TN-MOF-FAQ-952-INVOICE-NUMBER, TN-NC11-09-NUMBERING, TN-MOF-FAQ-75-NUMBERING | LIVE |
| client_address | 1 | 1 | TN-NC11-09-CLIENT, TN-MOF-FAQ-952-CLIENT, TN-NC11-09-SELLER | LIVE |
| dematerialized_invoice | 1 | 1 | TN-TVA23-18-ELECTRONIC, TN-MOF-FAQ-952-TRANSPORT, TN-NC11-09-REQUIRED-MENTIONS | LIVE |

The top-3 misses were `goods_description` and `price_before_tax`. Retrieval remains a candidate search for officer review.

## Lexical comparison on fixed paraphrases

| Case | Qdrant top-3 | Lexical top-3 | Qdrant top ID | Lexical top ID |
|---|---:|---:|---|---|
| continuous_numbering | 1 | 1 | TN-NC11-09-NUMBERING | TN-MOF-FAQ-75-NUMBERING |
| transport_record | 1 | 1 | TN-MOF-FAQ-952-TRANSPORT | TN-MOF-FAQ-75-GOODS-PRICE |
| non_vat_exception | 1 | 1 | TN-MOF-FAQ-75-TAX | TN-NC11-09-NON-VAT |
| delivery_slip | 1 | 1 | TN-NC11-09-GOODS-PRICE | TN-MOF-FAQ-75-TRANSPORT |
| series_no_gap | 1 | 1 | TN-MOF-FAQ-952-INVOICE-NUMBER | TN-MOF-FAQ-952-INVOICE-ISSUE |
| dematerialized_invoice | 1 | 0 | TN-TVA23-18-ELECTRONIC | TN-MOF-FAQ-952-INVOICE-NUMBER |

The dematerialized-invoice paraphrase returned `TN-TVA23-18-ELECTRONIC` at Qdrant rank 1; lexical did not return it in the top 3. Other comparisons were competitive. The full fixed query definitions and acceptable IDs are in `reference_eval.json`.
