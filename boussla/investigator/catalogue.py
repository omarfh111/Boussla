"""Fixed neutral candidate explanations. Selection is not a finding."""

HYPOTHESIS_CATALOGUE: dict[str, str] = {
    "SECOND_PROJECT_ALLOCATION": "Une autre affectation de projet pourrait expliquer l'écart de quantité.",
    "STOCK_REMAINING": "Un stock restant pourrait expliquer une différence d'affectation.",
    "PARTIAL_DELIVERY": "Une livraison partielle pourrait expliquer les pièces observées.",
    "CREDIT_NOTE_OR_REVERSAL": "Un avoir ou une annulation pourrait expliquer un montant différent.",
    "PAYMENT_SCHEDULE": "Un échéancier pourrait expliquer un règlement partiel.",
    "SELLER_TRANSCRIPTION_ERROR": "Une transcription côté vendeur pourrait être à vérifier.",
    "BUYER_TRANSCRIPTION_ERROR": "Une transcription côté acheteur pourrait être à vérifier.",
    "LATER_INVOICE_CORRECTION": "Une correction ultérieure de facture pourrait être à rechercher.",
    "UNIT_OR_ITEM_MAPPING_ISSUE": "L'unité ou le rapprochement des articles pourrait être à vérifier.",
    "MISSING_SUPPORTING_DOCUMENT": "Une pièce complémentaire pourrait être nécessaire pour conclure.",
}
