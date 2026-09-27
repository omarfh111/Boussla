"""Coverage and cutoffs are required for company-relative comparisons."""
from datetime import datetime, timezone
from decimal import Decimal
from boussla.behavior_profile import build_behavior_profile
from boussla.contracts import Perspective
from boussla.data.operational_portfolio import FIXTURE, seed_portfolio, case_facts
from boussla.portfolio_runtime import PortfolioRuntime

COMPANY = "SYN-OP-001"
AS_OF = datetime(2026, 1, 15, tzinfo=timezone.utc)

def facts():
    return case_facts(seed_portfolio(FIXTURE), COMPANY)

def coverage():
    return {f"2025-{m:02d}": f"COVER-{m}" for m in range(1, 13)}

def metric(profile, code, currency=None):
    return next(m for m in profile.metrics if m.code == code and m.currency == currency)

def test_requires_coverage_and_three_months_and_never_invents_cash():
    profile = build_behavior_profile(facts(), {}, AS_OF)
    assert all(m.status != "AVAILABLE" for m in profile.metrics)
    assert metric(profile, "CASH_FREQUENCY").current_value is None
    sparse = build_behavior_profile(facts(), {p:s for p,s in coverage().items() if p >= "2025-10"}, AS_OF)
    assert metric(sparse, "INVOICE_VOLUME").baseline_value is None

def test_monthly_baseline_uses_same_currency_and_sourced_values():
    data = facts()
    profile = build_behavior_profile(data, coverage(), AS_OF)
    amount = metric(profile, "MONTHLY_AMOUNT", "TND")
    assert amount.status == "AVAILABLE" and amount.sample_size == 6
    assert amount.source_ids and amount.baseline_periods == tuple(f"2025-{m:02d}" for m in range(6,12))
    txs = {t.transaction_id for t in data["transaction"] if t.economic_period == "2025-12"}
    expected = sum(o.gross_millimes for o in data["invoice_observation"] if o.transaction_id in txs and o.perspective is Perspective.BUYER_RECEIVED)
    assert Decimal(amount.current_value) == expected
    assert profile.observed_period == "2025-12" and profile.rule_version == "self-baseline-2"

def test_ambiguous_buyer_copies_invalidate_period_without_choosing_first():
    data = facts()
    txs = {t.transaction_id for t in data["transaction"] if t.economic_period == "2025-12"}
    buyer = next(o for o in data["invoice_observation"] if o.transaction_id in txs and o.perspective is Perspective.BUYER_RECEIVED)
    data["invoice_observation"] = [*data["invoice_observation"], buyer.model_copy(update={"observation_id":"COPY"})]
    result = metric(build_behavior_profile(data, coverage(), AS_OF), "INVOICE_VOLUME")
    assert result.current_value is None and result.status == "INSUFFICIENT_DATA"

def test_missing_current_coverage_and_future_documents_stay_unknown():
    data = facts()
    profile = build_behavior_profile(data, {p:s for p,s in coverage().items() if p != "2025-12"}, AS_OF)
    assert metric(profile, "MONTHLY_AMOUNT", "TND").current_value is None
    cutoff = datetime(2025, 5, 1, tzinfo=timezone.utc)
    profile = build_behavior_profile(data, coverage(), cutoff)
    allowed = {o.document_id for o in data["invoice_observation"] if o.available_at <= cutoff}
    assert all(ref in allowed or ref.startswith("COVER-") for ref in metric(profile,"INVOICE_VOLUME").source_ids)

def test_seasonality_uses_prior_year_of_observed_month_at_january_boundary():
    profile = build_behavior_profile(facts(), coverage(), AS_OF)
    seasonal = metric(profile, "SEASONALITY")
    assert seasonal.baseline_periods == ()
    assert seasonal.status == "INSUFFICIENT_DATA"

def test_signal_cache_respects_requested_cutoff(tmp_path, monkeypatch):
    calls = []
    def analyze(*args, **kwargs):
        calls.append(kwargs["as_of"])
        return ()
    monkeypatch.setattr("boussla.portfolio_runtime.analyze_self_history", analyze)
    runtime = PortfolioRuntime(tmp_path / "portfolio.json")
    early = datetime(2025,5,1,tzinfo=timezone.utc)
    runtime.signals(COMPANY, early)
    runtime.signals(COMPANY, early)
    runtime.signals(COMPANY)
    assert calls == [early, runtime.as_of]


def test_cash_frequency_requires_explicit_mode_for_every_observed_payment():
    data = facts()
    original = build_behavior_profile(data, coverage(), AS_OF)
    assert metric(original, "CASH_FREQUENCY").current_value is None
    data["payment"] = [p.model_copy(update={"payment_method":"CASH"}) for p in data["payment"]]
    result = metric(build_behavior_profile(data, coverage(), AS_OF), "CASH_FREQUENCY")
    assert result.current_value == "100" and result.baseline_value == "100"
    assert result.source_ids


def test_correction_count_excludes_plain_confirmations():
    from boussla.contracts import CaseEvent
    base = dict(case_id="C", actor_id="A", at=datetime(2025,12,20,tzinfo=timezone.utc),
                case_version=2, summary="Test", fact_ids=("EXTRACTION",))
    confirmation = CaseEvent(event_id="CONF",kind="TRANSCRIPTION_CONFIRMED",**base)
    correction = CaseEvent(event_id="CORR",kind="TRANSCRIPTION_CORRECTED",**base)
    assert metric(build_behavior_profile(facts(),coverage(),AS_OF,[confirmation]),"CORRECTION_ACTIVITY").current_value is None
    result = metric(build_behavior_profile(facts(),coverage(),AS_OF,[confirmation,correction]),"CORRECTION_ACTIVITY")
    assert result.current_value == "1" and "CORR" in result.source_ids and "CONF" not in result.source_ids


def test_anomaly_count_uses_evaluated_findings_not_missing_records():
    from boussla.contracts import Finding, FindingFamily, FindingStatus
    data = facts()
    transaction = next(t for t in data["transaction"] if t.economic_period == "2025-12")
    finding = Finding(finding_id="CAUSE",case_id="C",company_id=COMPANY,
        transaction_id=transaction.transaction_id,family=FindingFamily.COUNTERPARTY,
        status=FindingStatus.UNRESOLVED,calculation_version="TEST",case_version=1)
    unknown = metric(build_behavior_profile(data,coverage(),AS_OF),"ANOMALY_COUNT")
    assert unknown.current_value is None
    counted = metric(build_behavior_profile(data,coverage(),AS_OF,findings=[finding]),"ANOMALY_COUNT")
    assert counted.current_value == "1" and "CAUSE" in counted.source_ids
