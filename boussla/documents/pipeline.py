"""Source-bound document checks; reports propose review and never authorize facts."""
from datetime import date
from decimal import Decimal, InvalidOperation
from boussla.contracts import DocumentAnalysisReport, DocumentCheck

RULE_VERSION = "document-pipeline-1"


def analyze_document(document, extraction, routing, integrity, facts, findings, as_of, version, text=None):
    checks = []
    def check(code,status,message,sources=()):
        checks.append(DocumentCheck(code=code,status=status,explanation_fr=message,
                                    source_ids=tuple(dict.fromkeys((document.document_id,*sources)))))
    fields = {f.field_name:f for f in extraction.candidates} if extraction else {}
    usable = {name:f.normalized_value for name,f in fields.items()
              if f.normalized_value is not None and f.evidence_refs and not f.ambiguities
              and all(ref.document_id == document.document_id for ref in f.evidence_refs)}
    check("EXTRACTION", "PASS" if fields and len(usable) == len(fields) else "UNKNOWN",
          f"{len(usable)} champs sourcés sans ambiguïté sur {len(fields)} proposés.")
    def number(name):
        try:
            value = Decimal(usable[name])
            return value if value.is_finite() else None
        except (KeyError,InvalidOperation):
            return None
    net,tax,gross = (number(name) for name in ("net_millimes","tax_millimes","gross_millimes"))
    check("TOTAL_ARITHMETIC", "UNKNOWN" if None in (net,tax,gross) else "PASS" if net+tax == gross else "FAIL",
          "Vérification HT + taxe = TTC ; contrôle impossible lorsque les montants sont incomplets.")
    quantity,price,line_net = (number(name) for name in ("line_quantity","line_unit_price_millimes","line_net_millimes"))
    check("LINE_ARITHMETIC", "UNKNOWN" if None in (quantity,price,line_net) else "PASS" if abs(quantity*price-line_net) <= 1 else "FAIL",
          "Quantité × prix unitaire comparé au HT de la ligne, tolérance d’un millime.")
    rate = number("tax_rate")
    check("TAX_ARITHMETIC", "UNKNOWN" if None in (net,tax,rate) else "PASS" if abs(net*rate/100-tax) <= 1 else "FAIL",
          "Application arithmétique du taux déclaré ; ce contrôle ne valide pas le taux fiscal applicable.")
    issued = usable.get("issued_on")
    try:
        issued_date = date.fromisoformat(issued) if issued else None
        check("ISSUE_DATE", "UNKNOWN" if issued_date is None else "WARN" if issued_date > as_of.date() else "PASS",
              "Date documentaire comparée à la date d’analyse.")
    except ValueError:
        check("ISSUE_DATE","FAIL","Date non interprétable au format déclaré.")
    duplicate_ids = [d.document_id for d in facts.get("document",()) if d.document_id != document.document_id and d.sha256 == document.sha256]
    check("DUPLICATE_BYTES","WARN" if duplicate_ids else "PASS","Comparaison des empreintes dans ce dossier uniquement.",duplicate_ids)
    other_numbers = []
    if usable.get("invoice_number"):
        for other in facts.get("extraction",()):
            if other.document_id != document.document_id and any(c.field_name == "invoice_number" and c.normalized_value == usable["invoice_number"] for c in other.candidates):
                other_numbers.append(other.document_id)
    check("REPEATED_REFERENCE","WARN" if other_numbers else "UNKNOWN" if not usable.get("invoice_number") else "PASS",
          "Référence de facture déjà observée ; une répétition doit être examinée, pas automatiquement rejetée.",other_numbers)
    tx_ids = set()
    explicit = usable.get("allocation.transaction_id") or usable.get("transaction_id")
    known_transactions = {t.transaction_id:t for t in facts.get("transaction",())}
    if explicit in known_transactions:
        tx_ids.add(explicit)
    if usable.get("invoice_number"):
        matched = {o.transaction_id for o in facts.get("invoice_observation",())
                   if o.invoice_number == usable["invoice_number"] and o.available_at <= as_of and o.transaction_id in known_transactions}
        if len(matched) == 1:
            tx_ids |= matched
    declared_company = usable.get("allocation.company_id") or usable.get("company_id")
    if declared_company and declared_company != document.subject_company_id:
        tx_ids.clear()
        check("COMPANY_SCOPE","FAIL","L’entreprise déclarée ne correspond pas au dossier.")
    else:
        check("COMPANY_SCOPE","PASS" if declared_company else "UNKNOWN","Périmètre déclaré comparé au dossier ; identité non déduite du nom de fichier.")
    check("TRANSACTION_LINK","PASS" if len(tx_ids) == 1 else "UNKNOWN",
          "Lien candidat fondé sur une référence explicite et unique ; validation humaine requise.",sorted(tx_ids))
    external = [o for o in facts.get("invoice_observation",()) if o.transaction_id in tx_ids and o.document_id != document.document_id and o.available_at <= as_of]
    compared = [(o,name,str(getattr(o,name))) for o in external for name in ("invoice_number","currency","net_millimes","tax_millimes","gross_millimes") if name in usable]
    mismatches = [(o,name) for o,name,value in compared if value != usable[name]]
    check("DOSSIER_CONCORDANCE","WARN" if mismatches else "PASS" if compared else "UNKNOWN",
          "Comparaison aux observations documentaires du dossier ; aucun registre externe n’est consulté.",
          [o.document_id for o,_,_ in compared])
    proposals = [p for p in facts.get("proposal", ()) if p.source_document_id == document.document_id]
    coherence = []
    for proposal in proposals:
        from boussla.review_evidence import _allocation_coherence
        checked = extraction.model_copy(update={"status": "CONFIRMED"}) if extraction else None
        coherence.append(_allocation_coherence(proposal, document.document_id, checked, document.subject_company_id))
    check("RESPONSE_CONCORDANCE", "FAIL" if False in coherence else "PASS" if coherence and all(v is True for v in coherence) else "UNKNOWN",
          "Concordance technique des valeurs avec la réponse structurée ; elle ne remplace pas la confirmation humaine.",
          [p.proposal_id for p in proposals])
    check("SOURCE_STRUCTURE", "WARN" if any(f.ambiguities for f in fields.values()) else "UNKNOWN",
          "Les champs répétés incompatibles ou non interprétables nécessitent une revue ; aucune détection visuelle exhaustive n’est disponible.")
    metadata_status = "UNKNOWN"
    if integrity:
        created = integrity.metadata.get("pdf_creation_date", "").removeprefix("D:")[:8]
        modified = integrity.metadata.get("pdf_modification_date", "").removeprefix("D:")[:8]
        try:
            created_date = date.fromisoformat(f"{created[:4]}-{created[4:6]}-{created[6:8]}")
            modified_date = date.fromisoformat(f"{modified[:4]}-{modified[4:6]}-{modified[6:8]}")
            metadata_status = "WARN" if modified_date < created_date or created_date > document.received_at.date() else "PASS"
        except ValueError:
            pass
    check("METADATA_CHRONOLOGY", metadata_status,
          "Chronologie déclarée de création/modification et réception ; des métadonnées incohérentes constituent un signal à vérifier.")
    limitations = tuple(integrity.limitations) if integrity else ("INTEGRITY_NOT_RUN",)
    bad_hash = integrity is not None and integrity.sha256 != document.sha256
    check("BYTE_INTEGRITY","FAIL" if bad_hash else "UNKNOWN" if integrity is None or "INTEGRITY_ADAPTER_NOT_RUN" in limitations else "PASS",
          "L’empreinte contrôle la conservation des octets ; elle ne démontre pas l’authenticité.")
    check("VISUAL_ALTERATION","UNKNOWN","Analyse des zones visuelles altérées non disponible ; authenticité à vérifier.")
    from boussla.documents.labelled import classify_native
    class_name = routing.candidate_class.value if routing else classify_native(text).value
    if class_name == "OTHER_OR_UNKNOWN" and any(name.startswith("allocation.") for name in usable):
        class_name = "ALLOCATION_RESPONSE"
    families = {"PAYMENT_RECORD": {"SETTLEMENT"}, "INVOICE": {"COUNTERPARTY"},
                "ALLOCATION_RESPONSE": {"QUANTITY"}, "ALLOCATION_REFERENCE": {"QUANTITY"},
                "DELIVERY_RECORD": {"QUANTITY"}}.get(class_name, set())
    linked = tuple(sorted({f"{f.case_id}:{f.transaction_id}:{f.family.value}" for f in findings
                           if len(tx_ids) == 1 and f.transaction_id in tx_ids and f.family.value in families
                           and f.status.value == "UNRESOLVED"}))
    failed = any(c.status == "FAIL" for c in checks)
    stages = tuple(DocumentCheck(code=code,status=status,explanation_fr=description,source_ids=(document.document_id,))
        for code,status,description in (
            ("UPLOAD","PASS","Original conservé avec son empreinte."),
            ("CLASSIFICATION","PASS" if class_name != "OTHER_OR_UNKNOWN" else "UNKNOWN","Classe candidate, susceptible de correction."),
            ("EXTRACTION","PASS" if usable else "UNKNOWN","Champs proposés avec passages sources."),
            ("INTERNAL_CHECKS","WARN" if failed else "PASS" if usable else "UNKNOWN","Contrôles détaillés ci-dessous."),
            ("CASE_MATCHING","PASS" if tx_ids else "UNKNOWN","Rapprochement candidat au dossier."),
            ("EXTERNAL_CHECKS","UNKNOWN","Aucune vérification auprès d’un registre externe configurée."),
            ("AUTHENTICITY","UNKNOWN","Authenticité à vérifier."),
            ("CAUSE_LINKING","PASS" if linked else "UNKNOWN","Liens proposés uniquement, sans résolution automatique."),
            ("UPDATE_PROPOSAL","PASS","Examen humain proposé."),
            ("RECALCULATION","PASS","Calcul du dossier enregistré dans la même révision.")))
    return DocumentAnalysisReport(document_id=document.document_id,case_version=version,calculated_at=as_of,
        rule_version=RULE_VERSION,classification=class_name,checks=tuple(checks),stages=stages,
        linked_cause_ids=linked,transaction_ids=tuple(sorted(tx_ids)),
        proposed_action="REQUEST_READABLE_DOCUMENT" if not usable else "REQUEST_CLARIFICATION" if failed else "REVIEW_DOCUMENT",
        limitations=(*limitations,"NO_EXTERNAL_REGISTRY","NO_VISUAL_TAMPER_DETECTION"))
