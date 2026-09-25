"""Validate supplied fixture files, not the future BOUSSLA application."""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from decimal import Decimal
from pathlib import Path


def main(root: Path) -> dict:
    root = root.resolve()
    sys.path.insert(0, str(root / 'reference'))
    from core import Finding, quantity_excess, allocation_budget, score_transaction
    parsed_json = []
    for path in root.rglob('*.json'):
        # Avoid re-reading a generated report; validate actual inputs/config first.
        if path.name == 'pack_validation.json':
            continue
        json.loads(path.read_text(encoding='utf-8'))
        parsed_json.append(str(path.relative_to(root)))
    csv_counts = {}
    for path in (root/'fixtures/observed').glob('*.csv'):
        with path.open(encoding='utf-8', newline='') as handle:
            csv_counts[path.name] = len(list(csv.DictReader(handle)))
    obs=root/'fixtures/observed'
    read=lambda name: json.loads((obs/name).read_text(encoding='utf-8'))
    invoices=read('invoice_observations.json')
    assert len(invoices)==2 and len({x['transaction_id'] for x in invoices})==1
    for inv in invoices:
        assert inv['net_millimes']+inv['tax_millimes']==inv['gross_millimes']==4760000
        assert sum(line['line_net_millimes'] for line in inv['lines'])==inv['net_millimes']
        for line in inv['lines']:
            assert Decimal(line['quantity'])*line['unit_price_millimes']==line['line_net_millimes']
    assert invoices[0]['origin_group_id']!=invoices[1]['origin_group_id']
    assert read('payments.json')[0]['amount_millimes']==4760000
    assert read('payment_allocations.json')[0]['allocated_millimes']==4760000
    refs=read('quantity_references.json')
    assert len(refs)==2 and all(x['quantity']=='1000' for x in refs)
    q=quantity_excess('2000','1000',baseline_kind='APPROVED_PROCUREMENT_ALLOCATION',reference_accepted=True,units_match=True,scope_match=True)
    assert q['excess']=='1000'
    findings=[Finding('TX-001','COUNTERPARTY','EXPLAINED','0',('DOC-BUY-001','DOC-SELL-001')),Finding('TX-001','SETTLEMENT','EXPLAINED','0',('DOC-PAY-001',)),Finding('TX-001','QUANTITY','UNRESOLVED',q['severity'],('DOC-REF-001','CLAIM-001'))]
    before=score_transaction(findings,['COUNTERPARTY','SETTLEMENT','QUANTITY'])
    assert before['review_index']==40
    assert allocation_budget('2000',{'P1':'1000','P2':'1000'})['unallocated']=='0'
    after=score_transaction(findings[:2]+[Finding('TX-001','QUANTITY','EXPLAINED','0',('DOC-REF-001','DOC-ALLOC-001'))],['COUNTERPARTY','SETTLEMENT','QUANTITY'])
    assert after['review_index']==0
    try:
        allocation_budget('2000',{'P1':'2000','P2':'1000'})
    except ValueError:
        pass
    else:
        raise AssertionError('Expected allocation overflow rejection')
    from pypdf import PdfReader
    docs=read('documents.json'); pdf_reports=[]
    assert len(docs)==8
    for doc in docs:
        path=root/doc['relative_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==doc['sha256']
        pdf=PdfReader(path);assert len(pdf.pages)==1
        text=pdf.pages[0].extract_text()
        assert 'DÉMONSTRATION SYNTHÉTIQUE' in text and doc['document_id'] in text
        assert len(text)>350
        pdf_reports.append({'file':path.name,'pages':1,'extracted_characters':len(text),'sha256_matches':True})
    return {'status':'PASSED_FOR_FIXTURES_ONLY','json_files_parsed':len(parsed_json),'csv_row_counts':csv_counts,'pdfs':pdf_reports,'arithmetic_before':before,'arithmetic_after':after,'limitations':['No live extraction or provider API call.','No application, authentication, LangGraph, Qdrant or LangSmith integration was tested.','The manually specified evidence acceptance is a test premise, not document authentication.','Reference scoring is an illustrative heuristic, not real-world fraud validation.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path.cwd())
    args=parser.parse_args()
    print(json.dumps(main(args.root),ensure_ascii=False,indent=2))
