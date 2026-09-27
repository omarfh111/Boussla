from datetime import datetime, timezone
import pytest
from boussla.contracts import DocumentText, PageText, IntegrityReport, Finding, FindingFamily, FindingStatus
from boussla.documents.labelled import classify_native, extract_labelled
from boussla.documents.pipeline import analyze_document
from tests.checks.test_invoice_observations import _inputs


def text(body):
    return DocumentText(document_id="DOC-BUY-001", pages=(PageText(page=1,text=body),),status="OK")


@pytest.mark.parametrize("title,expected",[("Facture","INVOICE"),("Bon de livraison","DELIVERY_RECORD"),
    ("Paiement","PAYMENT_RECORD"),("Contrat","CONTRACT"),("Affectation","ALLOCATION_RESPONSE"),
    ("Déclaration","DECLARATION"),("Divers","OTHER_OR_UNKNOWN")])
def test_source_title_classifies_seven_document_families(title,expected):
    assert classify_native(text(title)).value == expected


def test_labelled_extraction_keeps_actual_spans_and_conflicts():
    result = extract_labelled(text("Facture\nRéférence : A1\nHT : 100,000 DT\nTVA : 19,000 DT\nTTC : 119,000 DT\nTTC : 129,000 DT"))
    fields = {f.field_name:f for f in result.candidates}
    assert fields["net_millimes"].normalized_value == "100000"
    assert fields["invoice_number"].evidence_refs[0].exact_text == "A1"
    assert fields["gross_millimes"].ambiguities == ("CONFLICTING_SOURCE_FIELDS",)


def report(body):
    inputs = _inputs()
    document = inputs.documents[0]
    native = text(body)
    extraction = extract_labelled(native)
    facts = {"transaction":[inputs.transaction],"invoice_observation":list(inputs.invoice_observations),
             "document":list(inputs.documents),"extraction":[extraction] if extraction else []}
    finding = Finding(finding_id="F",case_id=inputs.case_id,company_id=inputs.company_id,
        transaction_id=inputs.transaction.transaction_id,family=FindingFamily.COUNTERPARTY,
        status=FindingStatus.UNRESOLVED,case_version=1,calculation_version="TEST")
    integrity = IntegrityReport(document_id=document.document_id,sha256=document.sha256)
    return analyze_document(document,extraction,None,integrity,facts,[finding],inputs.as_of,2,native)


def test_checks_fail_arithmetic_without_claiming_forgery_or_resolving_anything():
    result = report("Facture\nTransaction : TX-001\nHT : 100,000 DT\nTVA : 19,000 DT\nTTC : 130,000 DT")
    checks = {c.code:c for c in result.checks}
    assert checks["TOTAL_ARITHMETIC"].status == "FAIL"
    assert result.proposed_action == "REQUEST_CLARIFICATION"
    assert result.authenticity_statement == "Authenticité à vérifier"
    assert result.linked_cause_ids == ("CASE-BRICKS-001:TX-001:COUNTERPARTY",)
    assert len(result.stages) == 10
    assert next(s for s in result.stages if s.code == "EXTERNAL_CHECKS").status == "UNKNOWN"


def test_wrong_company_and_unrelated_document_do_not_link_causes():
    result = report("Facture\nTransaction : TX-001\nEntreprise : OTHER")
    assert result.linked_cause_ids == () and result.transaction_ids == ()
    result = report("Contrat\nTransaction : TX-001")
    assert result.linked_cause_ids == ()


def test_no_usable_text_requests_a_readable_document_and_not_a_fraud_verdict():
    result = report("illisible")
    assert result.proposed_action == "REQUEST_READABLE_DOCUMENT"
    assert all(c.status != "PASS" for c in result.checks if c.code in ("EXTRACTION","TOTAL_ARITHMETIC"))
