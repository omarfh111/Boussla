"""Own-company baseline metrics with explicit coverage and comparable units."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from boussla.contracts import BehaviorMetric, BehaviorProfile, BehaviorSignal, Perspective

RULE_VERSION = "self-baseline-3"


def month(index):
    year, m = divmod(index, 12)
    return f"{year:04d}-{m + 1:02d}"


def mean(values):
    return sum(values, Decimal(0)) / len(values) if values else None


def build_behavior_profile(facts, coverage, as_of: datetime, events=(), findings=None) -> BehaviorProfile:
    if as_of.tzinfo is None:
        raise ValueError("timezone-aware cutoff required")
    current_index = as_of.year * 12 + as_of.month - 2
    current = month(current_index)
    prior = tuple(month(i) for i in range(current_index - 6, current_index))
    covered = {p for p, source in coverage.items() if source and p <= current}
    baseline = tuple(p for p in prior if p in covered)
    seasonal = tuple(month(current_index - 12 * year) for year in (1, 2))
    rows = {p: [] for p in (*seasonal, *prior, current)}
    transactions = {t.transaction_id: t for t in facts.get("transaction", ())}
    candidates = {}
    for invoice in facts.get("invoice_observation", ()):
        transaction = transactions.get(invoice.transaction_id)
        if (invoice.perspective is not Perspective.BUYER_RECEIVED or transaction is None
                or invoice.available_at > as_of or invoice.issued_on > as_of.date()
                or transaction.economic_period not in rows):
            continue
        # Multiple candidate buyer copies are ambiguous, never counted as extra purchases.
        candidates.setdefault(invoice.transaction_id, []).append(invoice)
    ambiguous_periods = set()
    for transaction_id, observations in candidates.items():
        period = transactions[transaction_id].economic_period
        if len(observations) != 1:
            ambiguous_periods.add(period)
        else:
            rows[period].append(observations[0])
    # Do not make an apparently smaller baseline from ambiguous buyer copies.
    covered -= ambiguous_periods
    baseline = tuple(p for p in prior if p in covered)
    metrics = []
    currencies = sorted({o.currency for group in rows.values() for o in group})
    def add(code, label, values, unit, currency=None, *, note="", sources=(), current_samples=None):
        value = values.get(current) if current in covered else None
        history = [values[p] for p in baseline if values.get(p) is not None]
        base = mean(history) if len(history) >= 3 else None
        change = ((value - base) / abs(base) * 100
                  if value is not None and base not in (None, Decimal(0)) else None)
        refs = tuple(sorted(set(sources) | {coverage[p] for p in (*baseline, current) if coverage.get(p)}))
        metrics.append(BehaviorMetric(code=code, label_fr=label, current_value=None if value is None else str(value),
            baseline_value=None if base is None else str(base), change_percent=None if change is None else str(change),
            status="AVAILABLE" if value is not None and base is not None else "INSUFFICIENT_DATA",
            unit=unit, currency=currency, baseline_periods=tuple(p for p in baseline if values.get(p) is not None), sample_size=len(history),
            current_sample_size=(current_samples.get(current, 0) if current_samples else 0), source_ids=refs,
            explanation_fr=note or "Période observée comparée à la moyenne des mois couverts précédents (au moins trois)."))
    invoice_refs = tuple(o.document_id for group in rows.values() for o in group)
    add("INVOICE_VOLUME", "Factures par mois", {p: Decimal(len(v)) for p, v in rows.items()}, "factures", sources=invoice_refs)
    add("SUPPLIER_COUNT", "Fournisseurs par mois", {p: Decimal(len({o.issuer_company_id for o in v if o.issuer_company_id}))
                                                   for p, v in rows.items()}, "fournisseurs", sources=invoice_refs)
    delay = {p: mean([Decimal((o.available_at.date() - o.issued_on).days) for o in v]) for p, v in rows.items()}
    add("DEPOSIT_DELAY", "Délai moyen de dépôt", delay, "jours", sources=invoice_refs)
    for currency in currencies:
        amounts = {p: [Decimal(o.gross_millimes) for o in v if o.currency == currency] for p, v in rows.items()}
        add("MONTHLY_AMOUNT", "Montant mensuel facturé", {p: sum(v, Decimal(0)) for p, v in amounts.items()}, "millimes", currency,
            sources=tuple(o.document_id for p in (*baseline, current) for o in rows[p] if o.currency == currency),
            current_samples={p: len(v) for p, v in amounts.items()})
        add("MEAN_INVOICE_AMOUNT", "Montant moyen des factures", {p: mean(v) for p, v in amounts.items()}, "millimes", currency, sources=invoice_refs)
        dispersion = {p: (mean([(a - mean(v)) ** 2 for a in v]).sqrt() if len(v) >= 2 else None) for p, v in amounts.items()}
        add("AMOUNT_DISPERSION", "Dispersion des montants (écart-type)", dispersion, "millimes", currency, sources=invoice_refs)
    payments = {p.payment_id: p for p in facts.get("payment", ())
                if p.status.value == "SETTLED" and p.occurred_at <= as_of and p.available_at <= as_of}
    by_transaction = {}
    for allocation in facts.get("payment_allocation", ()):
        if allocation.payment_id in payments and allocation.accepted_at <= as_of:
            by_transaction.setdefault(allocation.transaction_id, set()).add(allocation.payment_id)
    add("SPLIT_PAYMENTS", "Règlements observés par facture", {p: mean([Decimal(len(by_transaction.get(o.transaction_id, ())))
        for o in group]) for p, group in rows.items()}, "règlements", sources=tuple(payments),
        note="Nombre de règlements réglés et affectés observés ; zéro ne démontre pas l’absence de paiement hors des sources disponibles.")
    requests = {v.request.request_id: v.request for v in facts.get("request", ())}
    response_days = {p: [] for p in rows}
    response_sources = {p: [] for p in rows}
    for response in facts.get("response", ()):
        request = requests.get(response.request_id)
        available = (request.available_in_inbox_at or request.published_at) if request else None
        period = response.submitted_at.strftime("%Y-%m")
        if available is not None and available <= response.submitted_at <= as_of and period in response_days:
            delta = response.submitted_at - available
            response_days[period].append(Decimal(delta.days) + Decimal(delta.seconds) / 86400)
            response_sources[period].extend((request.request_id, response.response_id))
    add("RESPONSE_DELAY", "Délai moyen de réponse", {p: mean(v) for p, v in response_days.items()}, "jours",
        sources=tuple(source for p in (*baseline, current) for source in response_sources[p]),
        current_samples={p: len(v) for p, v in response_days.items()})
    decisions = {p: [] for p in rows}
    for proposal in facts.get("proposal", ()):
        if proposal.decided_at is not None and proposal.decided_at <= as_of and proposal.source_document_id:
            period = proposal.decided_at.strftime("%Y-%m")
            if period in decisions and proposal.status.value in ("ACCEPTED", "REJECTED"):
                decisions[period].append(proposal)
    add("DOCUMENT_REJECTION_RATE", "Taux de rejet des pièces examinées", {p: (Decimal(sum(x.status.value == "REJECTED" for x in v)) * 100 / len(v)
        if v else None) for p, v in decisions.items()}, "%", sources=tuple(x.proposal_id for v in decisions.values() for x in v))
    # Old confirmation events do not distinguish corrections: leave those months unknown.
    corrected = {p: [] for p in rows}
    for event in events:
        period = event.at.strftime("%Y-%m")
        if event.at <= as_of and period in rows:
            if event.kind == "TRANSCRIPTION_CORRECTED":
                corrected[period].append(event)
    add("CORRECTION_ACTIVITY", "Corrections de transcription attestées", {
        p: Decimal(len(v)) if v else None for p, v in corrected.items()}, "actions",
        sources=tuple(e.event_id for v in corrected.values() for e in v),
        note="Corrections enregistrées explicitement, sans compter les simples confirmations. Les anciennes confirmations non qualifiées restent inconnues.")
    known_suppliers = {o.issuer_company_id for p in baseline for o in rows[p] if o.issuer_company_id}
    new_suppliers = {o.issuer_company_id for o in rows[current] if o.issuer_company_id} - known_suppliers
    metrics.append(BehaviorMetric(code="NEW_SUPPLIERS", label_fr="Nouveaux fournisseurs", unit="fournisseurs",
        current_value=str(len(new_suppliers)) if current in covered and len(baseline) >= 3 else None,
        status="AVAILABLE" if current in covered and len(baseline) >= 3 else "INSUFFICIENT_DATA",
        baseline_periods=baseline, sample_size=len(baseline), source_ids=tuple(sorted(set(invoice_refs) | {coverage[p] for p in (*baseline, current) if coverage.get(p)})),
        explanation_fr="Fournisseurs absents des mois couverts de référence ; changement descriptif, pas une accusation."))
    cash_groups = {p: [] for p in rows}
    for payment in payments.values():
        period = payment.occurred_at.strftime("%Y-%m")
        if period in cash_groups:
            cash_groups[period].append(payment)
    add("CASH_FREQUENCY", "Fréquence des règlements en espèces", {
        p: Decimal(sum(x.payment_method == "CASH" for x in v)) * 100 / len(v)
        if v and all(x.payment_method != "UNKNOWN" for x in v) else None
        for p, v in cash_groups.items()}, "%", sources=tuple(payments),
        note="Part des règlements observés dont le mode est espèces ; inconnue dès qu’un mode manque dans le mois.")
    seasonal_periods = tuple(p for p in seasonal if p in covered)
    seasonal_base = mean([Decimal(len(rows[p])) for p in seasonal_periods]) if len(seasonal_periods) == 2 else None
    seasonal_current = Decimal(len(rows[current])) if current in covered else None
    metrics.append(BehaviorMetric(code="SEASONALITY", label_fr="Volume au même mois des années précédentes", unit="factures",
        current_value=str(seasonal_current) if seasonal_current is not None else None,
        baseline_value=str(seasonal_base) if seasonal_base is not None else None,
        change_percent=str((seasonal_current-seasonal_base)/seasonal_base*100) if seasonal_current is not None and seasonal_base else None,
        status="AVAILABLE" if seasonal_current is not None and seasonal_base is not None else "INSUFFICIENT_DATA",
        baseline_periods=seasonal_periods, sample_size=len(seasonal_periods),
        source_ids=tuple(sorted(set(invoice_refs) | {coverage[p] for p in (*seasonal_periods, current) if coverage.get(p)})),
        explanation_fr="Comparaison descriptive de deux mois homologues couverts ; ce n’est pas un modèle prédictif de saisonnalité."))
    anomaly_groups = {p: [] for p in rows}
    for finding in findings or ():
        transaction = transactions.get(finding.transaction_id)
        if transaction is not None and transaction.economic_period in anomaly_groups:
            anomaly_groups[transaction.economic_period].append(finding)
    add("ANOMALY_COUNT", "Causes non résolues par période de transaction", {
        p: Decimal(sum(f.status.value == "UNRESOLVED" for f in v)) if v else None
        for p, v in anomaly_groups.items()}, "causes",
        sources=tuple(f.finding_id for v in anomaly_groups.values() for f in v),
        note="État des causes évaluées au calcul courant, regroupées par période de transaction ; ce n’est pas une reconstruction de leur état passé.")
    signals = []
    for metric in metrics:
        if metric.code not in ("RESPONSE_DELAY", "MONTHLY_AMOUNT") or metric.status != "AVAILABLE":
            continue
        if metric.current_sample_size < 1 or metric.sample_size < 3:
            continue
        observed, usual = Decimal(metric.current_value), Decimal(metric.baseline_value)
        if usual <= 0 or observed < usual * 2:
            continue
        ratio = (observed / usual).quantize(Decimal("0.01"))
        limited = metric.current_sample_size < 3
        name = "Délai de réponse" if metric.code == "RESPONSE_DELAY" else "Montant mensuel facturé"
        signals.append(BehaviorSignal(
            code="RESPONSE_DELAY_DEVIATION" if metric.code == "RESPONSE_DELAY" else "MONTHLY_AMOUNT_DEVIATION",
            metric_code=metric.code, currency=metric.currency, observed_value=str(observed),
            baseline_value=str(usual), ratio=str(ratio),
            data_quality="LIMITED_DATA" if limited else "AVAILABLE", baseline_months=metric.sample_size,
            current_sample_size=metric.current_sample_size, source_ids=metric.source_ids,
            explanation_fr=f"{name} observé : {observed} {metric.unit} ; moyenne propre à l’entreprise : "
                           f"{usual} {metric.unit} sur {metric.sample_size} mois couverts (×{ratio}). "
                           + (f"Données limitées : {metric.current_sample_size} observation(s) du mois. " if limited else "")
                           + "Signal de revue descriptif, sans effet sur le score documentaire."))
    return BehaviorProfile(as_of=as_of, observed_period=current, baseline_periods=baseline,
                           rule_version=RULE_VERSION, metrics=tuple(metrics), signals=tuple(signals))
