import { useMemo, useState } from "react";
import { ArrowRight, Building2, CircleHelp, Search } from "lucide-react";
import type {
  Finding,
  HistoryView,
  Hypothesis,
  InvestigatorBrief,
  InvoiceComparison,
  InvoiceObservation,
  OfficerCaseView,
  QueueItem,
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
const pendingStatuses = new Set([
  "PENDING",
  "PUBLISHED_IN_DEMO",
  "AWAITING_RESPONSE",
]);
const serviceLabel: Record<string, string> = {
  NOT_REQUESTED: "Aucune demande",
  PUBLISHED_IN_DEMO: "En attente de réponse",
  RESPONDED: "Réponse reçue",
  ANSWERED: "Répondu",
  EXTENDED: "Échéance prolongée",
  CLOSED: "Clôturée",
  OVERDUE: "Suivi à revoir",
  PENDING: "En attente",
  UNRESOLVED: "À clarifier",
  SUPPORTED: "Étayée",
  CONTRADICTED: "Contredite",
  HYPOTHETICAL: "Hypothétique",
  SETTLED: "Réglé observé",
  ALLOCATION_RESPONSE: "Réponse d’affectation",
  STOCK_RECORD: "Pièce de stock",
  AMENDED_ALLOCATION_REFERENCE: "Référence d’affectation révisée",
};
const label = (value: string) =>
  serviceLabel[value] || value.replaceAll("_", " ");

export type PortfolioFilter =
  | "all"
  | "highest-triage"
  | "review-priority"
  | "clarification-pending"
  | "evidence-incomplete"
  | "history-anomaly";
export type PortfolioSort = "triage" | "review" | "activity" | "name";

export function selectPortfolio(
  items: QueueItem[],
  query: string,
  filter: PortfolioFilter,
  sector: string,
  sort: PortfolioSort,
): QueueItem[] {
  const maxTriage = Math.max(
    ...items.map((item) => item.triage?.rank ?? -Infinity),
  );
  const term = query.trim().toLocaleLowerCase("fr");
  return items
    .filter((item) => {
      if (
        term &&
        ![item.company_display_name, item.case_id, item.synthetic_identifier]
          .filter(Boolean)
          .some((value) => value!.toLocaleLowerCase("fr").includes(term))
      )
        return false;
      if (sector && item.sector !== sector) return false;
      if (filter === "highest-triage")
        return Number.isFinite(maxTriage) && item.triage?.rank === maxTriage;
      if (filter === "review-priority") return item.review_index !== null;
      if (filter === "clarification-pending")
        return pendingStatuses.has(item.clarification_status);
      if (filter === "evidence-incomplete")
        return item.coverage_complete === false;
      if (filter === "history-anomaly") return item.history_anomaly === true;
      return true;
    })
    .sort((a, b) => {
      const order =
        sort === "triage"
          ? (b.triage?.rank ?? -Infinity) - (a.triage?.rank ?? -Infinity)
          : sort === "review"
            ? (b.review_index ?? -Infinity) - (a.review_index ?? -Infinity)
            : sort === "activity"
              ? (b.last_activity_at ?? "").localeCompare(
                  a.last_activity_at ?? "",
                )
              : a.company_display_name.localeCompare(
                  b.company_display_name,
                  "fr",
                );
      return (
        order ||
        a.company_display_name.localeCompare(b.company_display_name, "fr")
      );
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
  const [sort, setSort] = useState<PortfolioSort>("review");
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
        label: "Triage le plus élevé",
        available: items.some((i) => i.triage),
      },
      {
        id: "review-priority",
        label: "Priorité de revue",
        available: items.some((i) => i.review_index !== null),
      },
      {
        id: "clarification-pending",
        label: "Clarification en attente",
        available: true,
      },
      {
        id: "evidence-incomplete",
        label: "Preuves incomplètes",
        available: items.some((i) => typeof i.coverage_complete === "boolean"),
      },
      {
        id: "history-anomaly",
        label: "Signal historique",
        available: items.some((i) => typeof i.history_anomaly === "boolean"),
      },
    ];
  return (
    <section className="portfolio-screen">
      <header className="portfolio-intro">
        <div>
          <span className="eyebrow">PORTEFEUILLE · DONNÉES SYNTHÉTIQUES</span>
          <h1>Portefeuille des entreprises</h1>
          <p>
            Vue des dossiers assignés et des signaux fournis par le service.
          </p>
        </div>
        <span className="portfolio-count">
          {items.length} dossier{items.length > 1 ? "s" : ""}
        </span>
      </header>
      <div className="portfolio-distinction">
        <div>
          <span>Triage / urgence</span>
          <strong>Signal distinct fourni par le service</strong>
        </div>
        <div>
          <span>Priorité de revue déterministe</span>
          <strong>Indice des contrôles documentaires</strong>
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
            <option value="review">Priorité de revue</option>
            <option value="triage">Triage</option>
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
                  <span>Triage / urgence</span>
                  <strong>
                    {item.triage ? item.triage.label_fr : "Non communiqué"}
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
                    {item.historical_signals?.length
                      ? item.historical_signals
                          .map((s) => s.label_fr)
                          .join(" · ")
                      : "Non communiqué"}
                  </strong>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
      <p className="portfolio-note">
        <CircleHelp size={15} /> Les valeurs absentes restent non communiquées.
        Le triage et la priorité de revue sont deux indicateurs distincts.
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
    <section className={`portfolio-card ${className}`}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function EmptyData({ children }: { children: React.ReactNode }) {
  return <p className="portfolio-no-data">{children}</p>;
}

export function Company360({
  c,
  history,
}: {
  c: OfficerCaseView;
  history: HistoryView | null;
}) {
  const profile = c.enterprise_profile;
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
          <strong>{show(profile?.synthetic_identifier ?? c.company_id)}</strong>
        </div>
        <div>
          <span>Période d’activité</span>
          <strong>
            {profile?.activity_period
              ? `${date(profile.activity_period.start)} — ${date(profile.activity_period.end)}`
              : "Non communiquée"}
          </strong>
        </div>
      </div>
      <div className="portfolio-columns">
        <Card title="Chronologie des factures">
          <ol className="portfolio-timeline">
            {c.transactions.map((tx) => (
              <li key={tx.transaction_id}>
                <span>{date(tx.issued_on)}</span>
                <strong>{show(tx.invoice_number)}</strong>
                <small>
                  {show(tx.counterparty_display_name)} · Facturé{" "}
                  {money(tx.invoiced_gross_millimes)}
                </small>
              </li>
            ))}
          </ol>
          {!c.transactions.length && (
            <EmptyData>Aucune facture observée.</EmptyData>
          )}
        </Card>
        <Card title="Règlements observés">
          <p className="portfolio-source">
            Source : données synthétiques fournies au dossier.
          </p>
          {c.payment_timeline?.length ? (
            <ol className="portfolio-timeline">
              {c.payment_timeline.map((payment) => (
                <li key={payment.payment_id}>
                  <span>{date(payment.occurred_at)}</span>
                  <strong>
                    {money(payment.amount_millimes, payment.currency ?? "TND")}
                  </strong>
                  <small>
                    {label(payment.status)} · {show(payment.origin_group_id)}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyData>
              Chronologie de paiement non fournie par le service.
            </EmptyData>
          )}
        </Card>
        <Card title="Activité par mois">
          {c.monthly_activity?.length ? (
            <div className="portfolio-months">
              {c.monthly_activity.map((month) => (
                <div key={month.month}>
                  <strong>{month.month}</strong>
                  <span>{month.transaction_count} transaction(s)</span>
                  <small>
                    Entrées : {money(month.inflow_millimes)} · Sorties :{" "}
                    {money(month.outflow_millimes)}
                  </small>
                  <small>Source : {month.source_label}</small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyData>
              Activité mensuelle non fournie par le service.
            </EmptyData>
          )}
        </Card>
        <Card title="Activité financière">
          <p className="portfolio-source">
            {c.financial_activity
              ? `Source synthétique : ${c.financial_activity.source_label}`
              : "Source : résumés de transactions synthétiques du dossier."}
          </p>
          {c.financial_activity ? (
            <dl className="portfolio-facts">
              <div>
                <dt>Règlements observés</dt>
                <dd>
                  {money(
                    c.financial_activity.observed_settlements_millimes,
                    c.financial_activity.currency,
                  )}
                </dd>
              </div>
              <div>
                <dt>Entrées</dt>
                <dd>
                  {money(
                    c.financial_activity.inflow_millimes,
                    c.financial_activity.currency,
                  )}
                </dd>
              </div>
              <div>
                <dt>Sorties</dt>
                <dd>
                  {money(
                    c.financial_activity.outflow_millimes,
                    c.financial_activity.currency,
                  )}
                </dd>
              </div>
            </dl>
          ) : c.transactions.some((item) => item.settled_millimes !== null) ? (
            <dl className="portfolio-facts">
              {c.transactions
                .filter((item) => item.settled_millimes !== null)
                .map((item) => (
                  <div key={item.transaction_id}>
                    <dt>Règlement observé · {show(item.invoice_number)}</dt>
                    <dd>{money(item.settled_millimes)}</dd>
                  </div>
                ))}
            </dl>
          ) : (
            <EmptyData>Aucun règlement observé fourni.</EmptyData>
          )}
        </Card>
        <Card title="Déclarations de contexte">
          {c.context_claims.length ? (
            <ol className="portfolio-timeline">
              {c.context_claims.map((claim) => (
                <li key={claim.claim_id}>
                  <span>{date(claim.submitted_at)}</span>
                  <strong>{claim.purpose_text}</strong>
                  <small>
                    {claim.beneficiary_type} · {claim.purpose_category}
                  </small>
                </li>
              ))}
            </ol>
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
        finding={c.findings.find((f) => f.family === "COUNTERPARTY") ?? null}
        comparison={c.invoice_comparison ?? null}
      />
    </section>
  );
}

export function InvoiceCompare({
  observations,
  finding,
  comparison,
}: {
  observations: InvoiceObservation[];
  finding: Finding | null;
  comparison: InvoiceComparison | null;
}) {
  const groups = new Map<
    string,
    { buyer: InvoiceObservation[]; seller: InvoiceObservation[] }
  >();
  for (const item of observations) {
    if (
      item.perspective !== "BUYER_RECEIVED" &&
      item.perspective !== "SELLER_ISSUED"
    )
      continue;
    const key =
      item.transaction_id ||
      `${item.issuer_company_id ?? "?"}:${item.invoice_number}:${item.issued_on}`;
    const group = groups.get(key) ?? { buyer: [], seller: [] };
    group[item.perspective === "BUYER_RECEIVED" ? "buyer" : "seller"].push(
      item,
    );
    groups.set(key, group);
  }
  const pairs = [...groups.entries()].flatMap(([key, group]) =>
    Array.from(
      { length: Math.max(group.buyer.length, group.seller.length) },
      (_, index) => ({
        key: `${key}:${index}`,
        buyer: group.buyer[index],
        seller: group.seller[index],
      }),
    ),
  );
  const matching =
    pairs.length === 1 &&
    !!pairs[0].buyer &&
    !!pairs[0].seller &&
    (comparison?.status === "MATCH" ||
      finding?.reason_code === "INDEPENDENT_INVOICE_VIEWS_MATCH");
  // A case-level comparison cannot attribute a field gap to a specific invoice
  // when several invoice pairs are present.
  const differences = new Set(
    pairs.length === 1 ? (comparison?.difference_fields ?? []) : [],
  );
  const field = (
    label: string,
    key: string,
    value: string | number | null | undefined,
  ) => (
    <div className={differences.has(key) ? "comparison-difference" : ""}>
      <dt>{label}</dt>
      <dd>{show(value)}</dd>
    </div>
  );
  const observation = (
    value: InvoiceObservation | undefined,
    title: string,
  ) => (
    <div className="comparison-side">
      <h3>{title}</h3>
      {value ? (
        <>
          <dl className="portfolio-facts">
            {field("Facture n°", "invoice_number", value.invoice_number)}
            {field("Date", "issued_on", date(value.issued_on))}
            {field("Devise", "currency", value.currency)}
            {field(
              "Net",
              "net_millimes",
              money(value.net_millimes, value.currency ?? "TND"),
            )}
            {field(
              "Taxe",
              "tax_millimes",
              money(value.tax_millimes, value.currency ?? "TND"),
            )}
            {field(
              "Brut",
              "gross_millimes",
              money(value.gross_millimes, value.currency ?? "TND"),
            )}
            {field(
              "Ligne",
              "lines",
              value.lines
                .map((line) => line.item_description || line.line_id)
                .join(" · "),
            )}
            {field(
              "Quantité",
              "quantity",
              value.lines.map((line) => line.quantity).join(" · "),
            )}
            {field(
              "Unité",
              "unit",
              value.lines.map((line) => line.unit).join(" · "),
            )}
            {field("Origine", "origin_group_id", value.origin_group_id)}
          </dl>
          <small className="portfolio-source">
            Pièce : {value.document_id}
          </small>
        </>
      ) : (
        <EmptyData>Observation non fournie.</EmptyData>
      )}
    </div>
  );
  return (
    <Card
      title="Facture · observation acheteur / vendeur"
      className="comparison-card"
    >
      <p className="portfolio-source">
        {matching
          ? "Observations concordantes selon le contrôle du service."
          : finding
            ? `Constat du service : ${show(finding.reason_code)} · ${finding.status}`
            : "Aucun constat de comparaison fourni."}
      </p>
      {pairs.length ? (
        pairs.map((pair) => (
          <div className="comparison-pair" key={pair.key}>
            {observation(pair.buyer, "Observation acheteur")}
            {observation(pair.seller, "Observation vendeur")}
          </div>
        ))
      ) : (
        <EmptyData>Aucune observation de facture fournie.</EmptyData>
      )}
      <p className="portfolio-note">
        Une concordance documentaire ne valide pas à elle seule la déclaration.
      </p>
    </Card>
  );
}

const evidence = (
  refs:
    | { document_id: string | null; source_record_id: string | null }[]
    | undefined,
) =>
  refs
    ?.map((ref) => ref.document_id || ref.source_record_id)
    .filter(Boolean)
    .join(" · ") || "Non fourni";
export function HypothesisCards({ hypotheses }: { hypotheses: Hypothesis[] }) {
  return (
    <Card title="Top hypothèses" className="hypothesis-panel">
      {hypotheses.length ? (
        <div className="hypothesis-grid">
          {hypotheses.slice(0, 5).map((hypothesis) => (
            <article key={hypothesis.hypothesis_id} className="hypothesis-card">
              <div className="hypothesis-head">
                <strong>
                  {hypothesis.name_fr || hypothesis.hypothesis_id}
                </strong>
                <span>{label(hypothesis.status)}</span>
              </div>
              <p>{hypothesis.scope}</p>
              {hypothesis.support_index !== null &&
                hypothesis.support_index !== undefined && (
                  <p>
                    <span>Support de l’hypothèse</span>{" "}
                    <strong>{hypothesis.support_index}</strong>
                  </p>
                )}
              <dl className="portfolio-facts">
                <div>
                  <dt>Éléments favorables</dt>
                  <dd>{evidence(hypothesis.supporting_refs)}</dd>
                </div>
                <div>
                  <dt>Éléments contraires</dt>
                  <dd>{evidence(hypothesis.contradicting_refs)}</dd>
                </div>
                <div>
                  <dt>Informations manquantes</dt>
                  <dd>
                    {hypothesis.missing_evidence_types.map(label).join(" · ") ||
                      "Aucune indiquée"}
                  </dd>
                </div>
              </dl>
            </article>
          ))}
        </div>
      ) : (
        <EmptyData>Aucune hypothèse fournie par le service.</EmptyData>
      )}
    </Card>
  );
}

function BriefList({ title, values }: { title: string; values: string[] }) {
  return (
    <section>
      <h3>{title}</h3>
      {values.length ? (
        <ul>
          {values.map((value, index) => (
            <li key={`${value}-${index}`}>{value}</li>
          ))}
        </ul>
      ) : (
        <EmptyData>Aucune information fournie.</EmptyData>
      )}
    </section>
  );
}
export function InvestigatorPanel({
  brief,
}: {
  brief: InvestigatorBrief | null | undefined;
}) {
  return (
    <Card title="Analyse assistée BOUSSLA" className="investigator-panel">
      <div className="investigator-head">
        <span className="eyebrow">
          AIDE À LA REVUE · {brief?.mode ?? "NON FOURNIE"}
        </span>
        <p>
          La synthèse reste attribuée au service et soumise à la revue de
          l’agent.
        </p>
      </div>
      {brief ? (
        <div className="investigator-grid">
          <BriefList
            title="Résumé"
            values={brief.summary_fr ? [brief.summary_fr] : []}
          />
          <BriefList
            title="Observations clés"
            values={brief.key_observations.map((item) => item.text_fr)}
          />
          <BriefList
            title="Top hypothèses"
            values={brief.top_hypotheses
              .slice(0, 5)
              .map((item) => item.name_fr || item.hypothesis_id)}
          />
          <BriefList
            title="Informations manquantes"
            values={brief.missing_information}
          />
          <BriefList
            title="Changements depuis la dernière version"
            values={brief.changes_since_last_version}
          />
          <BriefList
            title="Questions proposées / déjà posées"
            values={[
              ...brief.questions_proposed.map((value) => `Proposée : ${value}`),
              ...brief.questions_already_asked.map(
                (value) => `Déjà posée : ${value}`,
              ),
            ]}
          />
          <BriefList
            title="Références publiques candidates"
            values={brief.candidate_public_references.map(
              (item) => `${item.document_title} · ${item.rule_id}`,
            )}
          />
        </div>
      ) : (
        <EmptyData>
          Le service n’a pas fourni d’InvestigatorBrief pour cette version.
          Aucune analyse n’est simulée.
        </EmptyData>
      )}
    </Card>
  );
}

const outputLabels: Record<string, string> = {
  review_index: "Priorité hypothétique",
  hypothetical_review_index: "Priorité hypothétique",
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
    <Card title="Scénarios de sensibilité" className="scenario-panel">
      <div className="scenario-grid">
        <article className="scenario-card current">
          <span>État actuel</span>
          <strong>Priorité {show(reviewIndex)}</strong>
          <small>Valeur du dossier fournie par le service</small>
        </article>
        {scenarios.map((scenario) => (
          <article className="scenario-card" key={scenario.scenario_id}>
            <span>{scenario.label}</span>
            {Object.entries(scenario.outputs).map(([key, value]) => (
              <div key={key}>
                <small>{outputLabels[key] || key}</small>
                <strong>
                  {typeof value === "string"
                    ? label(value)
                    : show(typeof value === "number" ? value : null)}
                </strong>
              </div>
            ))}
          </article>
        ))}
      </div>
      <p className="portfolio-note">
        Simulation hypothétique — aucun changement du dossier.
      </p>
    </Card>
  );
}

export function DemoAdmin({ items }: { items: QueueItem[] }) {
  const enterprises = [
    ...new Map(
      items.map((item) => [item.company_id || item.case_id, item]),
    ).values(),
  ];
  return (
    <section className="company360">
      <header className="portfolio-intro">
        <div>
          <span className="eyebrow">DONNÉES SYNTHÉTIQUES</span>
          <h1>Administration de démonstration</h1>
          <p>
            Actions disponibles après publication d’une API autorisée par le
            service.
          </p>
        </div>
      </header>
      <Card title="Entreprises synthétiques visibles">
        <div className="admin-list">
          {enterprises.map((item) => (
            <div key={item.company_id || item.case_id}>
              <Building2 size={18} />
              <span>
                <strong>{item.company_display_name}</strong>
                <small>
                  {show(item.synthetic_identifier ?? item.company_id)} ·{" "}
                  {show(item.sector)}
                </small>
              </span>
              <button disabled title="API autorisée non disponible">
                Supprimer
              </button>
            </div>
          ))}
        </div>
        {!enterprises.length && (
          <EmptyData>
            Aucune entreprise renvoyée par la file de revue.
          </EmptyData>
        )}
      </Card>
      <Card title="Gestion du portefeuille">
        <div className="admin-actions">
          <button disabled>Initialiser le portefeuille</button>
          <button disabled>Réinitialiser le portefeuille</button>
          <button disabled>Ajouter une entreprise synthétique</button>
        </div>
        <p className="portfolio-note">
          Commandes désactivées : les points d’API autorisés ne sont pas exposés
          par la version actuelle.
        </p>
      </Card>
    </section>
  );
}
