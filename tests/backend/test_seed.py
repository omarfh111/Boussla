from boussla.contracts import Allocation, Document, InvoiceObservation
from boussla.seed import load_fixture_facts, seed_demo_case
from boussla.store import CaseStore


def test_seed_is_idempotent_and_versioned(tmp_path):
    store = CaseStore(tmp_path / "c.sqlite", tmp_path / "up")
    case = seed_demo_case(store)
    assert seed_demo_case(store) == case
    assert store.case_meta(case) == {"case_id": case, "company_id": "DEMO-BAT", "version": 1}
    assert len(store.facts(case, "invoice_observation", InvoiceObservation)) == 2
    assert store.facts(case, "allocation", Allocation)[0].quantity == "2000"
    docs = store.facts(case, "document", Document)
    assert {d.document_id for d in docs} == {"DOC-BUY-001", "DOC-SELL-001", "DOC-PAY-001", "DOC-REF-001", "DOC-DEL-001"}


def test_seed_never_reads_evaluation_truth():
    facts = load_fixture_facts()
    dumped = str({k: [m.model_dump() for m in v] for k, v in facts.items()})
    assert "evaluation_only" not in dumped and "expected_outcomes" not in dumped
    assert "DOC-ALLOC-001" not in dumped  # candidate response document is not initial evidence
