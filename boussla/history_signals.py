"""Neutral deterministic historical observations for human triage/context.

No scores, providers, hidden archetypes or writes. Thresholds are demo conventions,
not legal/payment deadlines. A covered zero month is distinct from missing coverage.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from statistics import median
from typing import Iterable, Mapping

from boussla.checks import ChecksEngineV4
from boussla.contracts import FindingFamily, FindingStatus, Perspective, TransactionInputs

SIGNAL_VERSION = "SYNTHETIC_HISTORY_V1"


@dataclass(frozen=True)
class HistorySignal:
    reason_code: str
    company_id: str
    period: str
    observed_value: str
    baseline_value: str | None
    metric: str
    baseline_periods: tuple[str, ...]
    evidence_source_ids: tuple[str, ...]
    explanation: str
    method: str = SIGNAL_VERSION
    affects_review_index: bool = False


def _month_number(period: str) -> int:
    parsed = date.fromisoformat(period + "-01")
    if parsed.strftime("%Y-%m") != period:
        raise ValueError("period must be YYYY-MM")
    return parsed.year * 12 + parsed.month - 1


def analyze_history(inputs: Iterable[TransactionInputs], *, company_id: str,
                    as_of: datetime, coverage: Mapping[str, str]) -> tuple[HistorySignal, ...]:
    """Analyze completed covered months available at an explicit cutoff.

coverage maps YYYY-MM to a source ID attesting complete *synthetic* ledger coverage.
Missing months are never imputed as zero. Duplicate or mixed-company inputs fail
closed. Invoice/payment views unavailable at cutoff do not enter metrics.
"""
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone aware")
    current_month = as_of.year*12 + as_of.month-1
    periods = sorted(p for p, source in coverage.items() if _month_number(p) < current_month and source)
    rows = {p: [] for p in periods}
    sources = {p: [coverage[p]] for p in periods}
    signals = []
    compared = False
    seen = set()
    engine = ChecksEngineV4()
    def emit(code, period, observed, baseline, metric, base_periods, ids, explanation):
        signals.append(HistorySignal(code, company_id, period, str(observed),
            None if baseline is None else str(baseline), metric, tuple(base_periods),
            tuple(sorted(set(ids))), explanation))
    for original in inputs:
        i = original.model_copy(update={"as_of": as_of})
        t = i.transaction
        if i.company_id != company_id or t.buyer_company_id != company_id or t.transaction_id in seen:
            raise ValueError("duplicate or cross-company history input")
        if any(o.buyer_company_id != company_id or o.transaction_id != t.transaction_id for o in i.invoice_observations):
            raise ValueError("cross-company invoice history")
        if any(p.payer_company_id != company_id for p in i.payments):
            raise ValueError("cross-company payment history")
        if any(d.subject_company_id != company_id or d.case_id != i.case_id for d in i.documents):
            raise ValueError("cross-company document history")
        seen.add(t.transaction_id)
        if t.economic_period not in rows:
            continue
        buyers = [o for o in i.invoice_observations if o.perspective is Perspective.BUYER_RECEIVED
                  and o.available_at <= as_of and o.issued_on <= as_of.date()]
        if len(buyers) != 1:
            continue
        invoice = buyers[0]
        refs = [t.transaction_id, invoice.document_id]
        payments = {p.payment_id: p for p in i.payments if p.status.value == "SETTLED"
                    and p.available_at <= as_of and p.occurred_at <= as_of and p.currency == invoice.currency}
        settled = sum(a.allocated_millimes for a in i.payment_allocations
                      if a.payment_id in payments and a.accepted_at <= as_of and a.transaction_id == t.transaction_id)
        refs += [p.source_record_id for p in payments.values()]
        findings = engine.evaluate_transaction(i)
        conflicts = [f for f in findings if f.family is FindingFamily.COUNTERPARTY and f.status is FindingStatus.UNRESOLVED]
        refs += [ref.document_id for f in conflicts for ref in f.evidence_refs if ref.document_id]
        rows[t.economic_period].append({"seller": t.seller_company_id, "gross": invoice.gross_millimes,
            "settled": settled, "conflict": bool(conflicts), "refs": refs, "currency": invoice.currency})
        sources[t.economic_period] += refs
        delay = (invoice.available_at.date()-invoice.issued_on).days
        if delay > 45:
            emit("LATE_DOCUMENT_ACTIVITY", t.economic_period, delay, 45, "days_until_buyer_document_available", (),
                 [invoice.document_id, t.transaction_id], "Pièce acheteur disponible plus de 45 jours après émission ; seuil descriptif, aucune conclusion sur la conformité.")
    def ids(ps):
        return [ref for p in ps for ref in sources[p]]
    for n, period in enumerate(periods):
        baseline = periods[max(0,n-3):n]
        consecutive = len(baseline) == 3 and _month_number(period)-_month_number(baseline[0]) == 3
        if not consecutive:
            continue
        compared = True
        mean = Decimal(sum(len(rows[p]) for p in baseline))/3
        count = len(rows[period])
        if mean >= 1 and count >= mean*3:
            emit("VOLUME_SPIKE", period, count, mean, "transaction_count", baseline, ids([*baseline,period]),
                 "Nombre de transactions au moins trois fois supérieur à la moyenne des trois mois couverts précédents ; à contextualiser.")
        if mean >= 1 and count <= mean/3:
            emit("VOLUME_DROP", period, count, mean, "transaction_count", baseline, ids([*baseline,period]),
                 "Nombre de transactions inférieur ou égal au tiers de la moyenne précédente ; aucune présomption de manquement.")
        previous = [r for p in baseline for r in rows[p]]
        current = rows[period]
        if previous and current and len({r["currency"] for r in previous+current}) == 1:
            def paid_ratio(group):
                gross = sum(r["gross"] for r in group)
                return Decimal(sum(r["settled"] for r in group))/gross if gross else None
            a, b = paid_ratio(previous), paid_ratio(current)
            if a is not None and b is not None and abs(a-b) >= Decimal("0.4"):
                emit("PAYMENT_PATTERN_CHANGE", period, b, a, "observed_settlement_to_gross_ratio", baseline,
                     ids([*baseline,period]), "La part observée des règlements change ; échéances inconnues, comparaison descriptive sans notion de retard exigible.")
    # Consecutive covered zero-activity months; no fabricated evidence for absence.
    run = []
    for period in [*periods, None]:
        contiguous = period is not None and (not run or _month_number(period) == _month_number(run[-1])+1)
        if period is not None and not rows[period] and contiguous:
            run.append(period)
            continue
        if len(run) >= 2:
            emit("ACTIVITY_GAP", f"{run[0]}/{run[-1]}", len(run), 0, "consecutive_covered_zero_activity_months", (), ids(run),
                 "Aucune transaction avec pièce acheteur disponible dans ces mois couverts du jeu synthétique ; explication humaine à recueillir.")
        run = [period] if period is not None and not rows[period] else []
    if len(periods) >= 6:
        previous_periods, latest_periods = periods[-6:-3], periods[-3:]
        if _month_number(periods[-1])-_month_number(periods[-6]) == 5:
            old = [r for p in previous_periods for r in rows[p]]
            new = [r for p in latest_periods for r in rows[p]]
            if old and new and all(r["seller"] for r in old+new):
                def concentration(group):
                    return Decimal(max(Counter(r["seller"] for r in group).values()))/len(group)
                a, b = concentration(old), concentration(new)
                if abs(a-b) >= Decimal("0.4"):
                    emit("COUNTERPARTY_CONCENTRATION_CHANGE", f"{latest_periods[0]}/{latest_periods[-1]}", b, a,
                         "largest_counterparty_transaction_share", previous_periods, ids(previous_periods+latest_periods),
                         "La part du fournisseur le plus représenté change entre deux trimestres couverts ; vérifier le contexte commercial.")
            conflicted = [r for r in new if r["conflict"]]
            if len(conflicted) >= 2:
                emit("REPEATED_INVOICE_CONFLICT", f"{latest_periods[0]}/{latest_periods[-1]}", len(conflicted),
                     sum(r["conflict"] for r in old), "distinct_transactions_with_invoice_conflicts", previous_periods,
                     ids(previous_periods+latest_periods), "Des observations indépendantes divergent sur plusieurs transactions distinctes ; revue humaine des pièces nécessaire.")
    if not signals:
        insufficient = not compared or not any(rows.values())
        emit("INSUFFICIENT_HISTORY" if insufficient else "NO_SIGNIFICANT_CHANGE",
             f"{periods[0]}/{periods[-1]}" if periods else "NO_COMPLETED_COVERED_PERIOD", sum(map(len,rows.values())),
             None, "observed_transactions", periods, ids(periods),
             "Historique couvert insuffisant pour les comparaisons." if insufficient else
             "Aucun seuil descriptif déclenché sur les périodes couvertes ; cela ne valide aucune déclaration.")
    return tuple(sorted(signals, key=lambda s: (s.period, s.reason_code, s.evidence_source_ids)))


def analyze_self_history(inputs: Iterable[TransactionInputs], *, company_id: str,
                         as_of: datetime, coverage: Mapping[str, str]) -> tuple[HistorySignal, ...]:
    """V2: neutral deviations from this company's own covered baseline.

    The V1 oracle stays stable. New observations require three consecutive covered
    prior months and attributable source IDs; no missing month is treated as zero.
    """
    items = tuple(inputs)
    legacy = analyze_history(items, company_id=company_id, as_of=as_of, coverage=coverage)
    current_month = as_of.year * 12 + as_of.month - 1
    periods = sorted(p for p, source in coverage.items() if source and _month_number(p) < current_month)
    rows: dict[str, list[dict]] = {p: [] for p in periods}
    for item in items:
        tx = item.transaction
        if tx.economic_period not in rows:
            continue
        buyers = [o for o in item.invoice_observations
                  if o.perspective is Perspective.BUYER_RECEIVED
                  and o.available_at <= as_of and o.issued_on <= as_of.date()]
        if len(buyers) != 1:
            continue
        buyer = buyers[0]
        settled_ids = {p.payment_id for p in item.payments if p.status.value == "SETTLED"
                       and p.available_at <= as_of and p.occurred_at <= as_of}
        payment_ids = {a.payment_id for a in item.payment_allocations
                       if a.payment_id in settled_ids and a.transaction_id == tx.transaction_id
                       and a.accepted_at <= as_of}
        rows[tx.economic_period].append({
            "transaction": tx.transaction_id, "document": buyer.document_id,
            "seller": tx.seller_company_id, "gross": buyer.gross_millimes,
            "currency": buyer.currency, "delay": max(0, (buyer.available_at.date()-buyer.issued_on).days),
            "payments": len(payment_ids), "payment_ids": payment_ids,
        })

    added: list[HistorySignal] = []

    def emit(code: str, period: str, observed: object, baseline: object, metric: str,
             baseline_periods: list[str], ids: list[str], explanation: str) -> None:
        added.append(HistorySignal(
            reason_code=code, company_id=company_id, period=period,
            observed_value=str(observed), baseline_value=str(baseline), metric=metric,
            baseline_periods=tuple(baseline_periods), evidence_source_ids=tuple(sorted(set(ids))),
            explanation=explanation, method="SYNTHETIC_SELF_HISTORY_V2"))

    for n, period in enumerate(periods):
        baseline_periods = periods[max(0, n-3):n]
        if (len(baseline_periods) != 3
                or _month_number(period)-_month_number(baseline_periods[0]) != 3):
            continue
        previous = [row for p in baseline_periods for row in rows[p]]
        if len(previous) < 3:
            continue
        base_refs = [coverage[p] for p in baseline_periods] + [r["transaction"] for r in previous]
        delay_base = median(r["delay"] for r in previous)
        payment_base = median(r["payments"] for r in previous)
        known_sellers = {r["seller"] for r in previous if r["seller"]}
        for current in rows[period]:
            refs = [*base_refs, coverage[period], current["transaction"], current["document"]]
            if current["delay"] >= delay_base + 10:
                emit("UNUSUAL_DEPOSIT_DELAY", period, current["delay"], delay_base,
                     "days_until_buyer_document_available", baseline_periods, refs,
                     "Délai de mise à disposition supérieur d'au moins 10 jours à l'habitude couverte de l'entreprise ; contexte à demander.")
            same_currency = [r["gross"] for r in previous if r["currency"] == current["currency"]]
            if len(same_currency) >= 3:
                amount_base = median(same_currency)
                if amount_base > 0 and current["gross"] >= amount_base * 2:
                    emit("UNUSUAL_AMOUNT_INCREASE", period, current["gross"], amount_base,
                         "buyer_invoice_gross_millimes", baseline_periods, refs,
                         "Montant au moins doublé par rapport à la médiane des pièces comparables ; explication commerciale à recueillir.")
                elif amount_base > 0 and current["gross"] <= amount_base / 2:
                    emit("UNUSUAL_AMOUNT_DECREASE", period, current["gross"], amount_base,
                         "buyer_invoice_gross_millimes", baseline_periods, refs,
                         "Montant inférieur à la moitié de la médiane des pièces comparables ; variation descriptive.")
            if current["seller"] and current["seller"] not in known_sellers:
                emit("NEW_SUPPLIER", period, current["seller"], len(known_sellers),
                     "seller_company_id", baseline_periods, refs,
                     "Fournisseur absent des trois mois couverts de référence ; vérifier le contexte, sans présumer d'une anomalie.")
            if current["payments"] >= 3 and current["payments"] >= payment_base + 2:
                emit("UNUSUAL_SPLIT_PAYMENT", period, current["payments"], payment_base,
                     "settled_payment_count_for_transaction", baseline_periods,
                     [*refs, *current["payment_ids"]],
                     "Plusieurs règlements observés pour une transaction, contrairement au schéma habituel couvert ; échéancier à vérifier.")
    if not added:
        return legacy
    return tuple(sorted((s for s in legacy if s.reason_code != "NO_SIGNIFICANT_CHANGE"),
                        key=lambda s: (s.period, s.reason_code, s.evidence_source_ids))) + tuple(
        sorted(added, key=lambda s: (s.period, s.reason_code, s.evidence_source_ids)))
