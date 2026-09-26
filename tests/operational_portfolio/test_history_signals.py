from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import json

import pytest

from boussla.checks import ChecksEngineV4
from boussla.contracts import FindingFamily, TransactionInputs
from boussla.data.operational_portfolio import FIXTURE, AS_OF, seed_portfolio, transaction_inputs
from boussla.history_signals import analyze_history

PORTFOLIO = seed_portfolio(FIXTURE)
ORACLE = json.loads((FIXTURE.parent / "evaluation_only/archetypes.json").read_text(encoding="utf-8"))
CUTOFF = datetime.fromisoformat(AS_OF)


def run(number, *, facts=None, cutoff=CUTOFF, coverage=None):
    cid = f"SYN-OP-{number:03d}"
    row = next(r for r in PORTFOLIO["enterprises"] if r["identity"]["company_id"] == cid)
    return analyze_history(transaction_inputs(PORTFOLIO,cid) if facts is None else facts,
        company_id=cid, as_of=cutoff, coverage=coverage if coverage is not None else
        {r["period"]:r["source_id"] for r in row["coverage"]})


@pytest.mark.parametrize("number", range(1,13))
def test_curated_signals_and_current_check_compatibility(number):
    cid = f"SYN-OP-{number:03d}"
    facts = transaction_inputs(PORTFOLIO,cid)
    before = [i.model_dump(mode="json") for i in facts]
    signals = run(number,facts=facts)
    assert sorted({s.reason_code for s in signals}) == ORACLE[cid]["signal_codes"]
    assert signals == run(number,facts=reversed(facts))
    assert all(s.period and s.metric and s.observed_value and s.explanation and s.evidence_source_ids for s in signals)
    assert all(not s.affects_review_index and s.company_id == cid for s in signals)
    assert all(ref.startswith(cid+"-") for s in signals for ref in s.evidence_source_ids)
    assert before == [i.model_dump(mode="json") for i in facts]
    engine = ChecksEngineV4()
    score = engine.score_transaction(engine.evaluate_transaction(facts[-1]),set(FindingFamily))
    assert score.review_index == ORACLE[cid]["last_review_index"]


def test_activity_gap_requires_covered_consecutive_months():
    signals = run(5)
    gap = next(s for s in signals if s.reason_code == "ACTIVITY_GAP")
    assert (gap.period,gap.observed_value) == ("2025-09/2025-10","2")
    coverage = {f"2025-{m:02d}":f"SYN-OP-005-COVERAGE-{m}" for m in range(1,13) if m != 10}
    assert "ACTIVITY_GAP" not in {s.reason_code for s in run(5,coverage=coverage)}
    assert {s.reason_code for s in run(5,coverage={})} == {"INSUFFICIENT_HISTORY"}


def test_cutoff_never_uses_future_invoices_payments_or_months():
    early = datetime(2025,8,1,tzinfo=timezone.utc)
    signals = run(5,cutoff=early)
    assert "LATE_DOCUMENT_ACTIVITY" not in {s.reason_code for s in signals}
    for s in signals:
        assert "2025-09" not in s.period and "2025-10" not in s.period
        assert not any("TX-008" in ref for ref in s.evidence_source_ids)
    assert {s.reason_code for s in run(1,cutoff=datetime(2025,1,1,tzinfo=timezone.utc))} == {"INSUFFICIENT_HISTORY"}


def test_spike_threshold_counts_transactions_not_invoice_views():
    facts = list(transaction_inputs(PORTFOLIO,"SYN-OP-006"))
    spike = next(s for s in run(6,facts=facts) if s.reason_code == "VOLUME_SPIKE")
    assert (spike.observed_value,spike.baseline_value) == ("4","1")
    assert "VOLUME_SPIKE" in {s.reason_code for s in run(6,facts=facts[:-1])}
    assert "VOLUME_SPIKE" not in {s.reason_code for s in run(6,facts=facts[:-2])}
    with pytest.raises(ValueError,match="duplicate"):
        run(6,facts=facts+[facts[0]])


def test_late_activity_boundary_and_payment_pattern_values():
    facts = list(transaction_inputs(PORTFOLIO,"SYN-OP-001"))
    original = facts[0]
    from datetime import timedelta
    for delay, expected in ((45,False),(46,True)):
        buyer = original.invoice_observations[0]
        changed = buyer.model_copy(update={"available_at": datetime.combine(buyer.issued_on,datetime.min.time(),timezone.utc)+timedelta(days=delay)})
        facts[0] = original.model_copy(update={"invoice_observations":(changed,original.invoice_observations[1])})
        assert ("LATE_DOCUMENT_ACTIVITY" in {s.reason_code for s in run(1,facts=facts)}) == expected
    payment = next(s for s in run(8) if s.reason_code == "PAYMENT_PATTERN_CHANGE")
    assert payment.period == "2025-10"
    assert (payment.observed_value,payment.baseline_value) == ("0.5","1")


def test_history_is_id_independent_and_has_no_archetype_shortcut():
    facts = transaction_inputs(PORTFOLIO,"SYN-OP-006")
    altered = [TransactionInputs.model_validate(json.loads(i.model_dump_json().replace("SYN-OP-006","SYN-RENAMED"))) for i in facts]
    result = analyze_history(altered,company_id="SYN-RENAMED",as_of=CUTOFF,
        coverage={f"2025-{m:02d}":f"SYN-RENAMED-COVERAGE-{m}" for m in range(1,13)})
    assert [(s.reason_code,s.period,s.observed_value,s.baseline_value) for s in result] == [
        (s.reason_code,s.period,s.observed_value,s.baseline_value) for s in run(6)]


@pytest.mark.parametrize("kind", ["company", "invoice", "payment", "document", "naive_cutoff"])
def test_scope_and_time_rejection(kind):
    facts = list(transaction_inputs(PORTFOLIO,"SYN-OP-001"))
    raw = facts[0].model_dump(mode="json")
    if kind == "company": raw["company_id"] = "SYN-OP-002"
    elif kind == "invoice": raw["invoice_observations"][0]["buyer_company_id"] = "SYN-OP-002"
    elif kind == "payment": raw["payments"][0]["payer_company_id"] = "SYN-OP-002"
    elif kind == "document": raw["documents"][0]["subject_company_id"] = "SYN-OP-002"
    facts[0] = TransactionInputs.model_validate(raw)
    with pytest.raises(ValueError):
        run(1,facts=facts,cutoff=datetime(2026,1,10) if kind == "naive_cutoff" else CUTOFF)


def test_sparse_coverage_is_insufficient_not_clean():
    result = run(1,coverage={f"2025-{m:02d}":f"SYN-OP-001-COV-{m}" for m in (1,3,7,12)})
    assert {s.reason_code for s in result} == {"INSUFFICIENT_HISTORY"}


def test_evaluation_artifact_matches_computed_facts():
    from boussla.data.operational_portfolio_evaluation import evaluate_operational_portfolio
    report = evaluate_operational_portfolio(PORTFOLIO)
    assert report["transaction_count"] == 147
    assert report["invoice_observation_count"] == 282
    assert report["buyer_seller_pairs"] == 135
    assert len(report["signal_codes"]) == 8
    assert report["signal_effect_on_review_index"] == "NONE"
    committed = FIXTURE.parents[2] / "results/operational_portfolio/summary.json"
    assert json.loads(committed.read_text(encoding="utf-8")) == json.loads(json.dumps(report))
