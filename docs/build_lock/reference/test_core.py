import unittest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from core import (Finding, to_millimes, decimal_value, corroboration_status,
                  score_transaction, enterprise_index, settlement_residual,
                  quantity_excess, allocation_budget, quantity_scenarios, follow_up_status)

class ReferenceChecks(unittest.TestCase):
    def test_money_exact(self):
        self.assertEqual(to_millimes('1234.567'), 1234567)
    def test_no_silent_round(self):
        with self.assertRaises(ValueError): to_millimes('1.2345')
    def test_no_float(self):
        with self.assertRaises(ValueError): decimal_value(0.1)
    def test_nonfinite(self):
        with self.assertRaises(ValueError): decimal_value('NaN')
    def test_common_source(self):
        self.assertEqual(corroboration_status(['company:1','company:1']), 'COMMON_ORIGIN')
    def test_distinct_origin_not_authenticity(self):
        self.assertIn('NOT_AUTHENTICITY',corroboration_status(['company:1','seller:2']))
    def test_missing_origin(self):
        self.assertEqual(corroboration_status(['company:1','']), 'ORIGIN_INSUFFICIENT')
    def test_score_quantity(self):
        f=Finding('T1','QUANTITY','UNRESOLVED','1',('DOC1',))
        self.assertEqual(score_transaction([f],['QUANTITY'])['review_index'],40)
    def test_score_resolved(self):
        f=Finding('T1','QUANTITY','EXPLAINED','0',('DOC1',))
        self.assertEqual(score_transaction([f],['QUANTITY'])['review_index'],0)
    def test_duplicate_finding_not_double(self):
        f=Finding('T1','QUANTITY','UNRESOLVED','1',('DOC1',))
        self.assertEqual(score_transaction([f,f],['QUANTITY'])['review_index'],40)
    def test_no_evaluable_null(self):
        f=Finding('T1','QUANTITY','INSUFFICIENT',None)
        self.assertIsNone(score_transaction([f],['QUANTITY'])['review_index'])
    def test_partial_coverage(self):
        f=Finding('T1','COUNTERPARTY','UNRESOLVED','1',('DOC1',))
        x=score_transaction([f],['COUNTERPARTY','QUANTITY'])
        self.assertEqual(x['review_index'],35);self.assertFalse(x['coverage_complete'])
        self.assertEqual(x['evidence_coverage'],'50.00')
    def test_no_evidence_no_score(self):
        with self.assertRaises(ValueError): score_transaction([Finding('T','QUANTITY','UNRESOLVED','1')],['QUANTITY'])
    def test_cross_transaction(self):
        with self.assertRaises(ValueError):
            score_transaction([Finding('T','QUANTITY','UNRESOLVED','1',('a',)),Finding('X','QUANTITY','UNRESOLVED','1',('b',))],['QUANTITY'])
    def test_company_not_diluted(self):
        self.assertEqual(enterprise_index([{'review_index':80}]+[{'review_index':0}]*99),80)
    def test_company_null(self):
        self.assertIsNone(enterprise_index([{'review_index':None}]))
    def test_initiated_payment_not_cash(self):
        r=settlement_residual(1000,[{'allocation_id':'P1','allocated_millimes':1000,'status':'INITIATED'}],mapping_confirmed=True,comparable_terms=True,source_complete=True)
        self.assertEqual(r['settled_millimes'],0)
    def test_duplicate_payment_observation(self):
        a={'allocation_id':'P1','allocated_millimes':1000,'status':'SETTLED'}
        r=settlement_residual(1000,[a,a],mapping_confirmed=True,comparable_terms=True,source_complete=True)
        self.assertEqual(r['residual_millimes'],0)
    def test_unknown_terms_not_adverse_residual(self):
        r=settlement_residual(1000,[],mapping_confirmed=True,comparable_terms=False,source_complete=True)
        self.assertIsNone(r['residual_millimes'])
    def test_unknown_mapping(self):
        r=settlement_residual(1000,[],mapping_confirmed=False,comparable_terms=True,source_complete=True)
        self.assertIsNone(r['residual_millimes'])
    def test_quantity_comparable(self):
        r=quantity_excess('2000','1000',baseline_kind='APPROVED_PROCUREMENT_ALLOCATION',reference_accepted=True,units_match=True,scope_match=True)
        self.assertEqual(r['excess'],'1000');self.assertEqual(r['severity'],'1')
    def test_user_estimate_no_points(self):
        r=quantity_excess('2000','1000',baseline_kind='USER_ESTIMATE',reference_accepted=True,units_match=True,scope_match=True)
        self.assertIsNone(r['severity'])
    def test_scope_mismatch(self):
        r=quantity_excess('2000','1000',baseline_kind='APPROVED_PROCUREMENT_ALLOCATION',reference_accepted=True,units_match=True,scope_match=False)
        self.assertIsNone(r['excess'])
    def test_allocations_balanced(self):
        self.assertEqual(allocation_budget('2000',{'P1':'1000','P2':'1000'})['unallocated'],'0')
    def test_no_double_allocation(self):
        with self.assertRaises(ValueError): allocation_budget('2000',{'P1':'2000','P2':'1000'})
    def test_scenarios_pure(self):
        r=quantity_scenarios('2000','1000',['0','0.10'])
        self.assertEqual(Decimal(r[1]['residual']),Decimal('900'))
        self.assertTrue(all(x['hypothetical'] and not x['changes_canonical_state'] for x in r))
    def test_late_valid_response(self):
        now=datetime(2026,9,25,tzinfo=timezone.utc)
        s=follow_up_status(now=now,target=now-timedelta(days=1),request_approved=True,available_to_company=True,service_available=True,responded=True,extension_requested=False)
        self.assertEqual(s,'RESPONSE_RECEIVED')
    def test_outage_not_overdue(self):
        now=datetime(2026,9,25,tzinfo=timezone.utc)
        s=follow_up_status(now=now,target=now-timedelta(days=1),request_approved=True,available_to_company=True,service_available=False,responded=False,extension_requested=False)
        self.assertEqual(s,'FOLLOW_UP_STATUS_UNKNOWN')
    def test_extension_request(self):
        now=datetime(2026,9,25,tzinfo=timezone.utc)
        s=follow_up_status(now=now,target=now-timedelta(days=1),request_approved=True,available_to_company=True,service_available=True,responded=False,extension_requested=True)
        self.assertEqual(s,'EXTENSION_REQUESTED')
    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            follow_up_status(now=datetime(2026,9,25),target=None,request_approved=True,available_to_company=True,service_available=True,responded=False,extension_requested=False)

if __name__=='__main__': unittest.main()
