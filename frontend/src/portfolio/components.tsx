import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Building2, CircleHelp, Search } from "lucide-react";
import { api } from "../api/client";
import type {
  AdminEnterprise,
  BriefHypothesis,
  HistorySignal,
  HistoryView,
  InvestigatorBrief,
  InvoiceComparison,
  InvoiceObservation,
  OfficerCaseView,
  QueueItem,
  RetrievedPassage,
  Scenario,
} from "../api/types";

const show = (value: string | number | null | undefined) =>
  value === null || value === undefined || value === ""
    ? "Non communiqué"
    : String(value);
const date = (value: string | null | undefined) =>
  value ? new Date(value).toLocaleDateString("fr-FR") : "Non communiqué";
const money = (value: number | null | undefined, currency = "TND") =>
  value === null || value === undefined
    ? "Non communiqué"
    : `${new Intl.NumberFormat("fr-TN", { minimumFractionDigits: 3, maximumFractionDigits: 3 }).format(value / 1000)} ${currency}`;
const pendingStatuses = new Set(["PENDING", "FOLLOW_UP_DUE"]);
const serviceLabel: Record<string, string> = {
  NOT_REQUESTED: "Aucune demande",
  PUBLISHED_IN_DEMO: "En attente de réponse",
  RESPONDED: "Réponse reçue",
  ANSWERED: "Répondu",
  EXTENDED: "Échéance prolongée",
  CLOSED: "Clôturée",
  PENDING: "En attente",
  FOLLOW_UP_DUE: "Relance à prévoir",
  UNRESOLVED: "À clarifier",
  EXPLAINED: "Expliqué",
  INSUFFICIENT: "Information insuffisante",
  SUPPORTED: "Étayée",
  PLAUSIBLE: "Plausible",
  WEAK: "Faiblement étayée",
  CONTRADICTED: "Contredite",
  HYPOTHETICAL: "Hypothétique",
  SETTLED: "Réglé observé",
  REVERSED: "Annulé",
  PARTIAL: "Partiel",
  ALLOCATION_RESPONSE: "Réponse d’affectation",
  STOCK_RECORD: "Pièce de stock",
  AMENDED_ALLOCATION_REFERENCE: "Référence d’affectation révisée",
};
export const label = (value: string) =>
  serviceLabel[value] || value.replaceAll("_", " ").toLowerCase();

/** Neutral French labels for lane B history codes (review context, never findings). */
export const historyLabel: Record<string, string> = {
  ACTIVITY_GAP: "Période sans activité documentée",
  LATE_DOCUMENT_ACTIVITY: "Pièces disponibles tardivement",
  VOLUME_SPIKE: "Hausse du volume",
  VOLUME_DROP: "Baisse du volume",
  PAYMENT_PATTERN_CHANGE: "Évolution des règlements observés",
  COUNTERPARTY_CONCENTRATION_CHANGE:
    "Évolution de la concentration fournisseurs",
  REPEATED_INVOICE_CONFLICT: "Divergences répétées entre observations",
  NO_SIGNIFICANT_CHANGE: "Aucun changement marquant",
  INSUFFICIENT_HISTORY: "Historique insuffisant",
};
/** Labels for the server's triage reason codes (the formula stays on the server). */
export const triageLabel: Record<string, string> = {
  REVIEW_FINDING_PRESENT: "Constat de revue présent",
  CLARIFICATION_PENDING: "Clarification en attente",
  CLARIFICATION_OVERDUE: "Relance à prévoir",
  REPEATED_UNANSWERED_CLARIFICATION: "Demandes répétées sans réponse",
  EVIDENCE_AWAITING_OFFICER_DECISION: "Décision de l’agent attendue",
  ACTIVITY_GAP_NEEDS_REVIEW: "Période sans activité à examiner",
  HISTORICAL_DATA_GAP_NEEDS_REVIEW: "Lacune historique à examiner",
  TRANSACTION_INCONSISTENCY_NEEDS_REVIEW:
    "Divergences de transactions à examiner",
  HISTORY_PATTERN_CHANGE_NEEDS_REVIEW: "Évolution historique à contextualiser",
};
export const questionName: Record<string, string> = {
  "Q-PROJECT-ALLOCATION": "Répartition des quantités par lot",
  "Q-SUPPORTING-DOC": "Pièce d’affectation ou de référence",
  "Q-PURPOSE": "Usage prévu",
  "Q-PROJECT-DATES": "Dates du projet",
  "Q-STOCK": "Quantité conservée en stock",
  "Q-COUNTERPART-RECORD": "Autre justificatif de l’opération",
  "Q-HORIZON-CONFIRM": "Confirmation de la période prévue",
  "Q-PROJECT-STAGE": "Phase du projet",
  "Q-PROJECT-BENEFICIARY": "Projet, lot ou bénéficiaire",
  "Q-PROJECT-REFERENCE": "Pièce de référence",
};
const fieldLabel: Record<string, string> = {
  invoice_number: "Facture n°",
  invoice_version: "Version",
  issued_on: "Date",
  currency: "Devise",
  net_millimes: "Net",
  tax_millimes: "Taxe",
  gross_millimes: "Brut",
  "line.item_description": "Ligne",
  "line.quantity": "Quantité",
  "line.unit": "Unité",
  "line.unit_price_millimes": "Prix unitaire",
  "line.line_net_millimes": "Net de ligne",
};

export type PortfolioFilter =
  | "all"
  | "highest-triage"
  | "review-priority"
  | "clarification-pending"
  | "evidence-incomplete"
  | "history-anomaly";
export type PortfolioSort = "triage" | "review" | "activity" | "name";

/** Client-side search/filter/sort over loaded rows, using server values only.
 * "triage" keeps the authoritative server order. */
export function selectPortfolio(
  items: QueueItem[],
  query: string,
  filter: PortfolioFilter,
  sector: string,
  sort: PortfolioSort,
): QueueItem[] {
  const maxTriage = Math.max(
    ...items.map((item) => item.triage_priority ?? -Infinity),
  );
  const term = query.trim().toLocaleLowerCase("fr");
  const filtered = items.filter((item) => {
    if (
      term &&
      ![item.company_display_name, item.case_id, item.synthetic_identifier]
        .filter(Boolean)
        .some((value) => value!.toLocaleLowerCase("fr").includes(term))
    )
      return false;
    if (sector && item.sector !== sector) return false;
    if (filter === "highest-triage")
      return Number.isFinite(maxTriage) && item.triage_priority === maxTriage;
    if (filter === "review-priority")
      return item.review_index !== null && item.review_index > 0;
    if (filter === "clarification-pending")
      return pendingStatuses.has(item.clarification_status);
    if (filter === "evidence-incomplete")
      return item.coverage_complete === false;
    if (filter === "history-anomaly") return item.history_anomaly === true;
    return true;
  });
  if (sort === "triage") return filtered; // server order: triage, index, activity, id
  return [...filtered].sort((a, b) => {
    const order =
      sort === "review"
        ? (b.review_index ?? -1) - (a.review_index ?? -1)
        : sort === "activity"
          ? (b.last_activity_at ?? "").localeCompare(a.last_activity_at ?? "")
          : a.company_display_name.localeCompare(b.company_display_name, "fr");
    return order || a.case_id.localeCompare(b.case_id);
  });
}

export function Portfolio({
  items,
  onOpen,
}: {
  items: QueueItem[];
  onOpen: (caseId: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<PortfolioFilter>("all");
  const [sector, setSector] = useState("");
  const [sort, setSort] = useState<PortfolioSort>("triage");
  const sectors = [
    ...new Set(
      items.map((item) => item.sector).filter((s): s is string => !!s),
    ),
  ].sort();
  const shown = useMemo(
    () => selectPortfolio(items, query, filter, sector, sort),
    [items, query, filter, sector, sort],
  );
  const filters: { id: PortfolioFilter; label: string; available: boolean }[] =
    [
      { id: "all", label: "Tous", available: true },
      {
        id: "highest-triage",
        label: "Urgence la plus élevée",
        available: items.some((i) => i.triage_priority !== null),
      },
      { id: "review-priority", label: "Constat de revue", available: true },
      {
        id: "clarification-pending",
        label: "Clarification en attente",
        available: true,
      },
      {
        id: "evidence-incomplete",
        label: "Preuves incomplètes",
        available: true,
      },
      {
        id: "history-anomaly",
        label: "Signal historique",
        available: items.some((i) => i.history_anomaly !== null),
      },
    ];
  return (
    <section className="portfolio-screen">
      <header className="portfolio-intro">
        <div>
          <span className="eyebrow">PORTEFEUILLE · DONNÉES SYNTHÉTIQUES</span>
          <h1>Portefeuille des entreprises</h1>
          <p>
            Dossiers assignés, ordonnés par urgence de traitement calculée par
            le service.
          </p>
        </div>
        <span className="portfolio-count">
          {items.length} dossier{items.length > 1 ? "s" : ""}
        </span>
      </header>
      <div className="portfolio-distinction">
        <div>
          <span>Urgence de traitement (triage)</span>
          <strong>
            Quoi examiner en premier — ni preuve, ni probabilité de fraude
          </strong>
        </div>
        <div>
          <span>Priorité de revue déterministe</span>
          <strong>Indice issu des contrôles documentaires</strong>
        </div>
      </div>
      <div className="portfolio-toolbar">
        <label className="portfolio-search">
          <Search size={17} />
          <span className="visually-hidden">Rechercher une entreprise</span>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Rechercher une entreprise ou un dossier"
          />
        </label>
        <label>
          Trier par
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as PortfolioSort)}
          >
            <option value="triage">Urgence (ordre du service)</option>
            <option value="review">Priorité de revue</option>
            <option value="activity">Dernière activité</option>
            <option value="name">Entreprise</option>
          </select>
        </label>
        <label>
          Secteur
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            disabled={!sectors.length}
          >
            <option value="">Tous les secteurs</option>
            {sectors.map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
      </div>
      <div
        className="portfolio-filters"
        role="group"
        aria-label="Filtres du portefeuille"
      >
        {filters.map((item) => (
          <button
            key={item.id}
            className={filter === item.id ? "active" : ""}
            disabled={!item.available}
            aria-pressed={filter === item.id}
            onClick={() => setFilter(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      {!shown.length ? (
        <div className="portfolio-empty">
          Aucun dossier pour cette recherche ou ce filtre.
        </div>
      ) : (
        <div className="portfolio-results" role="list">
          {shown.map((item) => (
            <article
              className="portfolio-card-item"
              role="listitem"
              key={item.case_id}
            >
              <div className="portfolio-card-top">
                <div className="portfolio-enterprise">
                  <Building2 size={22} />
                  <span>
                    <strong>{item.company_display_name}</strong>
                    <small>
                      {item.case_id} · v{item.case_version} ·{" "}
                      {show(item.sector)}
                    </small>
                  </span>
                </div>
                <button
                  className="portfolio-open"
                  onClick={() => onOpen(item.case_id)}
                  aria-label={`Ouvrir ${item.company_display_name}`}
                >
                  Ouvrir l’entreprise <ArrowRight size={17} />
                </button>
              </div>
              <div className="portfolio-card-metrics">
                <div>
                  <span>Urgence (triage)</span>
                  <strong className="portfolio-triage">
                    {show(item.triage_priority)}
                  </strong>
                </div>
                <div>
                  <span>Priorité de revue déterministe</span>
                  <strong className="portfolio-index">
                    {show(item.review_index)}
                  </strong>
                </div>
                <div>
                  <span>Couverture des preuves</span>
                  <strong>
                    {item.evidence_coverage === null
                      ? "Non communiqué"
                      : `${item.evidence_coverage} %`}
                  </strong>
                </div>
                <div>
                  <span>Constats actifs</span>
                  <strong>{item.active_finding_count}</strong>
                </div>
              </div>
              {item.triage_reason_codes.length > 0 && (
                <div className="tags triage-reasons">
                  {item.triage_reason_codes.map((code) => (
                    <span className="badge" key={code}>
                      {triageLabel[code] || code}
                    </span>
                  ))}
                </div>
              )}
              <div className="portfolio-card-foot">
                <div>
                  <span>Clarification</span>
                  <strong>{label(item.clarification_status)}</strong>
                </div>
                <div>
                  <span>Dernière activité</span>
                  <strong>{date(item.last_activity_at)}</strong>
                </div>
                <div>
                  <span>Signaux historiques</span>
                  <strong>
                    {item.history_signal_codes.length
                      ? item.history_signal_codes
                          .map((c) => historyLabel[c] || c)
                          .join(" · ")
                      : "Aucun historique synthétique"}
                  </strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <p className="portfolio-note">
        <CircleHelp size={15} /> L’urgence (triage) et la priorité de revue sont
        deux indicateurs distincts calculés par le service ; une absence de
        réponse ne crée aucun constat.
      </p>
    </section>
  );
}

function Card({
  title,
  children,
  className = "",
}: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`portfolio-card enter-once ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function EmptyData({ children }: { children: React.ReactNode }) {
  return <p className="portfolio-no-data">{children}</p>;
}

export function HistorySignals({ signals }: { signals: HistorySignal[] }) {
  return (
    <Card
      title="Signaux historiques (contexte de revue)"
      className="history-signals"
    >
      <p className="portfolio-source">
        Observations synthétiques neutres — ce ne sont ni des constats ni des
        indices de fraude.
      </p>
      {signals.length ? (
        <ul className="signal-list">
          {signals.map((s) => (
            <li key={s.signal_id}>
              <div>
                <strong>{historyLabel[s.reason_code] || s.reason_code}</strong>
                <span className="mono">{s.period}</span>
              </div>
              <p>{s.explanation_fr}</p>
              <small>
                Observé : {s.observed_value}
                {s.baseline_value !== null
                  ? ` · Référence : ${s.baseline_value}`
                  : ""}{" "}
                · {s.evidence_source_ids.length} source(s) synthétique(s)
              </small>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyData>
          Aucun historique synthétique pour cette entreprise.
        </EmptyData>
      )}
    </Card>
  );
}

export function Company360({
  c,
  history,
}: {
  c: OfficerCaseView;
  history: HistoryView | null;
}) {
  const profile = c.enterprise_profile;
  const maxMonth = Math.max(
    1,
    ...c.monthly_activity
      .filter((m) => m.coverage_status === "COVERED")
      .map((m) => m.transaction_count),
  );
  const pairs = c.invoice_comparisons.filter(
    (x) => x.status !== "SINGLE_OBSERVATION",
  );
  return (
    <section className="company360">
      <header className="portfolio-intro">
        <div>
          <span className="eyebrow">ENTREPRISE 360 · DONNÉES SYNTHÉTIQUES</span>
          <h1>{c.company_display_name}</h1>
          <p>
            {c.case_id} · version {c.case_version}
          </p>
        </div>
      </header>
      <div className="portfolio-profile">
        <div>
          <span>Secteur</span>
          <strong>{show(profile?.sector)}</strong>
        </div>
        <div>
          <span>Identifiant synthétique</span>
          <strong>{show(profile?.synthetic_identifier)}</strong>
        </div>
        <div>
          <span>Période d’activité</span>
          <strong>
            {profile?.activity_start
              ? `${profile.activity_start} — ${show(profile.activity_end)}`
              : "Non communiquée"}
          </strong>
        </div>
        <div>
          <span>Nature des données</span>
          <strong>Synthétiques</strong>
        </div>
      </div>
      <div className="metric-grid four enter-once">
        <div className="metric">
          <span>Factures observées</span>
          <strong>{c.invoice_observations.length}</strong>
          <small>{c.transactions.length} transaction(s)</small>
        </div>
        <div className="metric">
          <span>Paires acheteur / vendeur</span>
          <strong>{pairs.length}</strong>
          <small>
            {pairs.filter((x) => x.status === "DIFFERENCES").length} avec
            différences
          </small>
        </div>
        <div className="metric">
          <span>Règlements observés</span>
          <strong>{c.payment_timeline.length}</strong>
          <small>Chronologie synthétique</small>
        </div>
        <div className="metric">
          <span>Déclarations de contexte</span>
          <strong>{c.context_claims.length}</strong>
          <small>Affirmations attribuées</small>
        </div>
      </div>
      <Card title="Habitude vs période actuelle">
        {c.behavior_profile ? (
          <>
            <p className="portfolio-source">
              Période observée : {c.behavior_profile.observed_period} ·{" "}
              {c.behavior_profile.baseline_periods.length} mois de référence
              couverts · règle {c.behavior_profile.rule_version}
            </p>
            {!!c.behavior_profile.signals?.length && (
              <div
                className="history-comparisons"
                aria-label="Écarts à examiner"
              >
                {c.behavior_profile.signals.map((signal) => (
                  <article key={`${signal.code}:${signal.currency ?? "all"}`}>
                    <strong>
                      {signal.code === "RESPONSE_DELAY_DEVIATION"
                        ? "Délai de réponse inhabituel"
                        : "Montant mensuel inhabituel"}
                    </strong>
                    <p>{signal.explanation_fr}</p>
                    <small>
                      {signal.data_quality === "LIMITED_DATA"
                        ? "Données limitées"
                        : "Comparaison disponible"}{" "}
                      · {signal.current_sample_size} observation(s) actuelles ·{" "}
                      {signal.baseline_months} mois de référence
                    </small>
                    <details>
                      <summary>Sources du signal</summary>
                      <small>{signal.source_ids.join(", ")}</small>
                    </details>
                  </article>
                ))}
              </div>
            )}
            <div className="history-comparisons">
              {c.behavior_profile.metrics.map((metric) => (
                <article key={`${metric.code}:${metric.currency ?? "all"}`}>
                  <strong>
                    {metric.label_fr}
                    {metric.currency ? ` · ${metric.currency}` : ""}
                  </strong>
                  <div>
                    <span>
                      Actuel{" "}
                      <b>
                        {metric.current_value ?? "inconnu"}{" "}
                        {metric.current_value === null ? "" : metric.unit}
                      </b>
                    </span>
                    <span>
                      Habitude{" "}
                      <b>
                        {metric.baseline_value ?? "données insuffisantes"}{" "}
                        {metric.baseline_value === null ? "" : metric.unit}
                      </b>
                    </span>
                  </div>
                  <small>
                    {metric.change_percent !== null
                      ? `Écart : ${metric.change_percent} %`
                      : "Écart non calculable"}{" "}
                    · {metric.sample_size} mois exploitables
                  </small>
                  <details>
                    <summary>Méthode et sources</summary>
                    <p>{metric.explanation_fr}</p>
                    <small>
                      {metric.source_ids.join(", ") || "Sources insuffisantes"}
                    </small>
                  </details>
                </article>
              ))}
            </div>
          </>
        ) : (
          <EmptyData>
            Baseline propre à cette entreprise indisponible : comparaison non
            calculable.
          </EmptyData>
        )}
      </Card>
      <Card title="Activité sur 12 mois">
        {c.monthly_activity.length ? (
          <div
            className="month-bars"
            role="list"
            aria-label="Transactions par mois"
          >
            {c.monthly_activity.map((m) => (
              <div
                role="listitem"
                key={m.month}
                title={
                  m.coverage_status === "COVERED"
                    ? `${m.month} : ${m.transaction_count} transaction(s) · ${m.source_label}`
                    : `${m.month} : couverture inconnue`
                }
              >
                {m.coverage_status === "COVERED" ? (
                  <span
                    className="month-bar"
                    style={{
                      height: `${(m.transaction_count / maxMonth) * 100}%`,
                    }}
                  />
                ) : (
                  <span className="month-unknown">?</span>
                )}
                <strong>
                  {m.coverage_status === "COVERED" ? m.transaction_count : "—"}
                </strong>
                <small>{m.month.slice(5)}</small>
              </div>
            ))}
          </div>
        ) : (
          <EmptyData>Aucune activité mensuelle dans le dossier.</EmptyData>
        )}
        <p className="portfolio-source">
          Source : faits synthétiques du dossier ; un mois absent n’est jamais
          compté comme nul.
        </p>
      </Card>
      <HistorySignals signals={c.history_signals} />
      <div className="portfolio-columns">
        <Card title="Chronologie des factures">
          <details>
            <summary>
              {c.transactions.length} transaction(s) — afficher le détail
            </summary>
            <ol className="portfolio-timeline">
              {c.transactions.map((tx) => (
                <li key={tx.transaction_id}>
                  <span>{date(tx.issued_on)}</span>
                  <strong>{show(tx.invoice_number)}</strong>
                  <small>
                    {show(tx.counterparty_display_name ?? tx.transaction_id)} ·
                    Facturé {money(tx.invoiced_gross_millimes)} · Réglé observé{" "}
                    {money(tx.settled_millimes)}
                  </small>
                </li>
              ))}
            </ol>
          </details>
        </Card>
        <Card title="Règlements observés">
          {c.payment_timeline.length ? (
            <details>
              <summary>
                {c.payment_timeline.length} règlement(s) — afficher le détail
              </summary>
              <ol className="portfolio-timeline">
                {c.payment_timeline.map((payment) => (
                  <li key={payment.payment_id}>
                    <span>{date(payment.occurred_at)}</span>
                    <strong>
                      {money(payment.amount_millimes, payment.currency)}
                    </strong>
                    <small>
                      {label(payment.status)} · {payment.origin_group_id}
                    </small>
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <EmptyData>Aucun règlement observé.</EmptyData>
          )}
        </Card>
        <Card title="Activité financière">
          {c.financial_snapshot ? (
            <>
              <p className="snapshot-label">{c.financial_snapshot.label_fr}</p>
              <dl className="portfolio-facts">
                <div>
                  <dt>Règlements observés</dt>
                  <dd>
                    {money(c.financial_snapshot.observed_settlements_millimes)}
                  </dd>
                </div>
                <div>
                  <dt>Sorties observées</dt>
                  <dd>
                    {money(c.financial_snapshot.observed_outflows_millimes)}
                  </dd>
                </div>
                <div>
                  <dt>Montant documenté à payer</dt>
                  <dd>
                    {money(c.financial_snapshot.documented_payable_millimes)}
                  </dd>
                </div>
                <div>
                  <dt>Reste documenté (non exigible établi)</dt>
                  <dd>
                    {money(
                      c.financial_snapshot
                        .outstanding_documented_payable_millimes,
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Entrées</dt>
                  <dd>Non fournies (périmètre achats uniquement)</dd>
                </div>
              </dl>
              <p className="portfolio-source">
                {c.financial_snapshot.statement_fr}
              </p>
            </>
          ) : (
            <EmptyData>
              Aucun instantané financier synthétique pour cette entreprise.
              BOUSSLA n’accède à aucun compte bancaire.
            </EmptyData>
          )}
        </Card>
        <Card title="Déclarations de contexte">
          {c.context_claims.length ? (
            <details>
              <summary>
                {c.context_claims.length} déclaration(s) — afficher
              </summary>
              <ol className="portfolio-timeline">
                {c.context_claims.map((claim) => (
                  <li key={claim.claim_id}>
                    <span>{date(claim.submitted_at)}</span>
                    <strong>{claim.purpose_text}</strong>
                    <small>
                      {claim.project_id
                        ? `Projet ${claim.project_id}`
                        : "Sans projet"}{" "}
                      · {label(claim.purpose_category)}
                    </small>
                  </li>
                ))}
              </ol>
            </details>
          ) : (
            <EmptyData>Aucune déclaration de contexte.</EmptyData>
          )}
        </Card>
        <Card title="Révisions du dossier">
          {history?.revisions.length ? (
            <ol className="portfolio-timeline">
              {[...history.revisions].reverse().map((revision) => (
                <li key={revision.version}>
                  <span>{date(revision.created_at)}</span>
                  <strong>Version {revision.version}</strong>
                  <small>{revision.reason}</small>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyData>Historique non disponible.</EmptyData>
          )}
        </Card>
      </div>
      <InvoiceCompare
        observations={c.invoice_observations}
        comparisons={c.invoice_comparisons}
      />
    </section>
  );
}

const observationValue = (o: InvoiceObservation, field: string) => {
  const line = o.lines[0];
  switch (field) {
    case "issued_on":
      return date(o.issued_on);
    case "net_millimes":
    case "tax_millimes":
    case "gross_millimes":
      return money(o[field], o.currency);
    case "line.item_description":
      return show(line?.item_description);
    case "line.quantity":
      return show(line?.quantity);
    case "line.unit":
      return show(line?.unit);
    case "line.unit_price_millimes":
      return money(line?.unit_price_millimes, o.currency);
    case "line.line_net_millimes":
      return money(line?.line_net_millimes, o.currency);
    default:
      return show((o as unknown as Record<string, string | null>)[field]);
  }
};

function ComparisonPair({
  comparison,
  byId,
}: {
  comparison: InvoiceComparison;
  byId: Map<string, InvoiceObservation>;
}) {
  const buyer = comparison.buyer_observation_id
    ? byId.get(comparison.buyer_observation_id)
    : undefined;
  const seller = comparison.seller_observation_id
    ? byId.get(comparison.seller_observation_id)
    : undefined;
  const differences = new Set(comparison.difference_fields);
  const side = (value: InvoiceObservation | undefined, title: string) => (
    <div className="comparison-side">
      <h3>{title}</h3>
      {value ? (
        <>
          <dl className="portfolio-facts">
            {Object.keys(fieldLabel).map((field) => (
              <div
                key={field}
                className={
                  differences.has(field) ? "comparison-difference" : ""
                }
              >
                <dt>{fieldLabel[field]}</dt>
                <dd>{observationValue(value, field)}</dd>
              </div>
            ))}
            <div>
              <dt>Source / origine</dt>
              <dd>{value.origin_group_id}</dd>
            </div>
          </dl>
          {value.lines.length > 1 && (
            <details>
              <summary>Toutes les lignes ({value.lines.length})</summary>
              {value.lines.map((line) => (
                <p key={line.line_id}>
                  {line.item_description} · {line.quantity} {line.unit} · Prix
                  unitaire {money(line.unit_price_millimes, value.currency)} ·
                  HT {money(line.line_net_millimes, value.currency)}
                </p>
              ))}
            </details>
          )}
          <small className="portfolio-source">
            Pièce : {value.document_id}
          </small>
        </>
      ) : (
        <EmptyData>Observation non disponible.</EmptyData>
      )}
    </div>
  );
  return (
    <div className="comparison-block">
      <p className={`comparison-status ${comparison.status.toLowerCase()}`}>
        <strong>{comparison.label_fr}</strong> · {comparison.transaction_id}
      </p>
      {comparison.reconciliation_status === "RAPPROCHEMENT_AMBIGU" && (
        <p>Candidates : {comparison.candidate_observation_ids?.join(", ")}</p>
      )}
      {comparison.difference_fields.length > 0 && (
        <p>Champs différents : {comparison.difference_fields.join(", ")}</p>
      )}
      {comparison.rule_version && (
        <small>Règle : {comparison.rule_version}</small>
      )}
      <div className="comparison-pair">
        {side(buyer, "Observation acheteur")}
        {side(seller, "Observation vendeur")}
      </div>
    </div>
  );
}

export function InvoiceCompare({
  observations,
  comparisons,
}: {
  observations: InvoiceObservation[];
  comparisons: InvoiceComparison[];
}) {
  const byId = new Map(observations.map((o) => [o.observation_id, o]));
  const ordered = [
    ...comparisons.filter((x) => x.status === "DIFFERENCES"),
    ...comparisons.filter((x) => x.status !== "DIFFERENCES"),
  ];
  const [first, ...rest] = ordered;
  return (
    <Card
      title="Facture · observation acheteur / vendeur"
      className="comparison-card"
    >
      <p className="portfolio-source">
        Appariement par identifiant de transaction ; seules les différences
        calculées par le service sont surlignées.
      </p>
      {first ? (
        <>
          <ComparisonPair comparison={first} byId={byId} />
          {rest.length > 0 && (
            <details className="comparison-more">
              <summary>Afficher les {rest.length} autre(s) paire(s)</summary>
              {rest.map((comparison) => (
                <ComparisonPair
                  key={comparison.transaction_id}
                  comparison={comparison}
                  byId={byId}
                />
              ))}
            </details>
          )}
        </>
      ) : (
        <EmptyData>Aucune observation de facture fournie.</EmptyData>
      )}
      <p className="portfolio-note">
        Des observations concordantes renforcent la corroboration ; elles ne
        prouvent ni l’authenticité ni la validité juridique.
      </p>
    </Card>
  );
}

export function HypothesisCards({
  hypotheses,
}: {
  hypotheses: BriefHypothesis[];
}) {
  return (
    <Card title="Top hypothèses" className="hypothesis-panel">
      <p className="portfolio-source">
        Catalogue fixe d’explications neutres ; le statut est un libellé de
        support, jamais une probabilité.
      </p>
      {hypotheses.length ? (
        <div className="hypothesis-grid">
          {hypotheses.slice(0, 5).map((h) => (
            <article key={h.hypothesis_id} className="hypothesis-card">
              <div className="hypothesis-head">
                <strong>{h.name_fr}</strong>
                <span>Support de l’hypothèse : {label(h.status)}</span>
              </div>
              <p>{h.why_it_matters_fr}</p>
              <dl className="portfolio-facts">
                <div>
                  <dt>Éléments favorables</dt>
                  <dd>{h.supporting_refs.join(" · ") || "Aucun"}</dd>
                </div>
                <div>
                  <dt>Éléments contraires</dt>
                  <dd>{h.contradicting_refs.join(" · ") || "Aucun"}</dd>
                </div>
                <div>
                  <dt>Informations manquantes</dt>
                  <dd>
                    {h.missing_evidence.map(label).join(" · ") ||
                      "Aucune indiquée"}
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <EmptyData>Aucune hypothèse à examiner pour cette version.</EmptyData>
      )}
    </Card>
  );
}

function BriefList({
  title,
  values,
  limit = 8,
}: {
  title: string;
  values: string[];
  limit?: number;
}) {
  const item = (value: string, index: number) => (
    <li key={`${value}-${index}`}>{value}</li>
  );
  return (
    <section className="brief-section">
      <h3>{title}</h3>
      {values.length ? (
        <>
          <ul>{values.slice(0, limit).map(item)}</ul>
          {values.length > limit && (
            <details>
              <summary>
                Afficher {values.length - limit} élément(s) de plus
              </summary>
              <ul>{values.slice(limit).map((v, i) => item(v, i + limit))}</ul>
            </details>
          )}
        </>
      ) : (
        <EmptyData>Aucune information.</EmptyData>
      )}
    </section>
  );
}
export function InvestigatorPanel({
  brief,
  passages,
}: {
  brief: InvestigatorBrief | null | undefined;
  passages: RetrievedPassage[];
}) {
  const refs = new Set(brief?.reference_rule_ids ?? []);
  return (
    <Card title="Analyse assistée BOUSSLA" className="investigator-panel">
      <div className="investigator-head">
        <span className="eyebrow">
          AIDE À LA REVUE ·{" "}
          {brief
            ? brief.mode === "LIVE"
              ? "MODÈLE"
              : "REPLI DÉTERMINISTE"
            : "NON DISPONIBLE"}
        </span>
        <p className="investigator-disclaimer">
          L'analyse assistée ne modifie pas l'indice de revue ni les faits du
          dossier.
        </p>
      </div>
      {brief ? (
        <div
          className="investigator-grid"
          key={`${brief.case_id}-${brief.case_version}`}
        >
          <BriefList title="Résumé" values={[brief.summary_fr]} />
          <BriefList
            title="Observations clés"
            values={brief.key_observations.map((item) => item.text_fr)}
          />
          <BriefList
            title="Top hypothèses"
            values={brief.top_hypotheses
              .slice(0, 5)
              .map((h) => `${h.name_fr} — ${label(h.status)}`)}
          />
          <BriefList
            title="Informations manquantes"
            values={brief.missing_information.map(label)}
          />
          <BriefList
            title="Changements depuis la version précédente"
            values={brief.changes_since_previous_version}
          />
          <BriefList
            title="Questions proposées / déjà posées"
            values={[
              ...brief.questions_proposed.map(
                (q) => `Proposée : ${questionName[q] || q}`,
              ),
              ...brief.questions_already_asked.map(
                (q) => `Déjà posée : ${questionName[q] || q}`,
              ),
            ]}
          />
          <BriefList
            title="Références publiques candidates"
            values={passages
              .filter((p) => refs.has(p.rule_id))
              .map((p) => `${p.document_title} · ${p.rule_id}`)}
          />
          <BriefList title="Limitations" values={brief.limitations} />
        </div>
      ) : (
        <EmptyData>
          Aucune analyse assistée pour cette version. Aucune analyse n’est
          simulée.
        </EmptyData>
      )}
    </Card>
  );
}

const outputLabels: Record<string, string> = {
  current_review_index: "Indice de revue actuel",
  hypothetical_review_index: "Indice de revue hypothétique",
  quantity_status_after: "Écart de quantité (simulation)",
  residual_units: "Unités résiduelles",
  unit: "Unité",
  status: "Statut",
};
export function ScenarioCards({
  reviewIndex,
  scenarios,
}: {
  reviewIndex: number | null | undefined;
  scenarios: Scenario[];
}) {
  return (
    <Card title="Scénarios hypothétiques" className="scenario-panel">
      <div className="scenario-grid">
        <article className="scenario-card current">
          <span>État actuel</span>
          <strong>Indice de revue {show(reviewIndex)}</strong>
          <small>Valeur canonique du dossier</small>
        </article>
        {scenarios.map((scenario) => {
          const hypothetical = scenario.outputs.hypothetical_review_index;
          return (
            <article className="scenario-card" key={scenario.scenario_id}>
              <span>{scenario.label}</span>
              {hypothetical !== undefined && (
                <strong className="scenario-shift">
                  {show(scenario.outputs.current_review_index ?? reviewIndex)}
                  <ArrowRight size={18} className="scenario-arrow" />
                  {hypothetical}
                </strong>
              )}
              {Object.entries(scenario.outputs)
                .filter(([key]) => key !== "status")
                .map(([key, value]) => (
                  <div key={key}>
                    <small>{outputLabels[key] || key}</small>
                    <strong>{label(String(value))}</strong>
                  </div>
                ))}
            </article>
          );
        })}
      </div>
      <p className="portfolio-note">
        Simulation hypothétique — aucun changement du dossier.
      </p>
    </Card>
  );
}

export function DemoAdmin({ enabled }: { enabled: boolean }) {
  const client = useQueryClient();
  const list = useQuery({
    queryKey: ["admin", "enterprises"],
    queryFn: () => api.admin.list(),
    enabled,
  });
  const [name, setName] = useState("");
  const [sector, setSector] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);
  const run = async (job: () => Promise<unknown>, success: string) => {
    if (pending) return;
    setPending(true);
    try {
      await job();
      setNotice(success);
      await client.invalidateQueries({ queryKey: ["admin"] });
      await client.invalidateQueries({ queryKey: ["queue"] });
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Action impossible.");
    } finally {
      setPending(false);
    }
  };
  const items: AdminEnterprise[] = list.data?.items ?? [];
  return (
    <section className="company360">
      <header className="portfolio-intro">
        <div>
          <span className="eyebrow">OPÉRATEUR DÉMO · DONNÉES SYNTHÉTIQUES</span>
          <h1>Administration de démonstration</h1>
          <p className="admin-notice">
            Administration de données synthétiques — démonstration locale.
          </p>
        </div>
      </header>
      {!enabled ? (
        <EmptyData>Réservé au rôle « Opérateur démo ».</EmptyData>
      ) : (
        <>
          {notice && (
            <p className="toast inline" role="status">
              {notice}
            </p>
          )}
          <Card title={`Entreprises synthétiques (${items.length})`}>
            <div className="admin-list">
              {items.map((item) => (
                <div key={item.company_id}>
                  <Building2 size={18} />
                  <span>
                    <strong>{item.display_name}</strong>
                    <small>
                      {item.synthetic_identifier} · {item.sector} ·{" "}
                      {item.transaction_count} transaction(s) · {item.case_id}
                    </small>
                  </span>
                  <button
                    className="danger"
                    disabled={pending}
                    onClick={() => {
                      if (
                        window.confirm(
                          `Supprimer l’entreprise synthétique ${item.company_id} et son dossier de démonstration ?`,
                        )
                      )
                        void run(
                          () => api.admin.remove(item.company_id),
                          `Entreprise synthétique ${item.company_id} supprimée.`,
                        );
                    }}
                  >
                    Supprimer
                  </button>
                </div>
              ))}
            </div>
            {list.isLoading && <EmptyData>Chargement…</EmptyData>}
          </Card>
          <Card title="Ajouter une entreprise synthétique">
            <form
              className="form-grid"
              onSubmit={(e) => {
                e.preventDefault();
                void run(
                  () => api.admin.add(name, sector),
                  "Entreprise synthétique ajoutée au portefeuille.",
                ).then(() => {
                  setName("");
                  setSector("");
                });
              }}
            >
              <label>
                Nom
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  maxLength={80}
                />
              </label>
              <label>
                Secteur
                <input
                  value={sector}
                  onChange={(e) => setSector(e.target.value)}
                  required
                  maxLength={60}
                />
              </label>
              <button className="primary" disabled={pending}>
                Ajouter
              </button>
            </form>
          </Card>
          <Card title="Gestion du portefeuille">
            <div className="admin-actions">
              <button
                disabled={pending}
                onClick={() =>
                  void run(
                    () => api.admin.seed(),
                    "Dossiers manquants initialisés.",
                  )
                }
              >
                Initialiser les dossiers manquants
              </button>
              <button
                className="danger"
                disabled={pending}
                onClick={() => {
                  if (
                    window.confirm(
                      "Réinitialiser le portefeuille synthétique ? Toutes les modifications des 12 dossiers synthétiques et les entreprises ajoutées seront supprimées.",
                    )
                  )
                    void run(
                      () => api.admin.reset(),
                      "Portefeuille synthétique réinitialisé.",
                    );
                }}
              >
                Réinitialiser le portefeuille (destructif)
              </button>
            </div>
            <p className="portfolio-note">
              Données synthétiques uniquement. Le dossier de démonstration
              principal n’est jamais modifié par ces actions.
            </p>
          </Card>
        </>
      )}
    </section>
  );
}
