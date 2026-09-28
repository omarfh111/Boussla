import {
  Component,
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  useInfiniteQuery,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Building2,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Database,
  FileText,
  FolderOpen,
  History,
  LayoutDashboard,
  RefreshCw,
  Search,
  UploadCloud,
} from "lucide-react";
import { ApiError, api } from "./api/client";
import { NetworkGraph3D } from "./network/NetworkGraph3D";
import { BootSplash, shouldShowBoot } from "./brand/BootSplash";
import { BousslaMark } from "./brand/BousslaMark";
import {
  Company360,
  DemoAdmin,
  HypothesisCards,
  InvestigatorPanel,
  InvoiceCompare,
  Portfolio,
  ScenarioCards,
  triageLabel,
} from "./portfolio/components";
import type {
  Role,
  CompanyCaseView,
  OfficerCaseView,
  EvidenceProposal,
  RevisionResult,
  Finding,
  HistoryView,
  Mode,
  RequestView,
  ClarificationDraft,
  DocumentView,
  ContextAssessmentView,
  InvestigationAnswer,
} from "./api/types";

type Tab =
  | "overview"
  | "operations"
  | "context"
  | "requests"
  | "documents"
  | "queue"
  | "company360"
  | "dossier"
  | "references"
  | "history"
  | "diagnostics"
  | "admin"
  | "network"
  | "notifications"
  | "messages"
  | "advanced";
const companyTabs: [Tab, string, ReactNode][] = [
  ["overview", "Mes dossiers", <LayoutDashboard size={18} />],
  ["requests", "Actions requises", <FolderOpen size={18} />],
  ["documents", "Documents", <FileText size={18} />],
  ["messages", "Messages", <ClipboardList size={18} />],
];
const officerTabs: [Tab, string, ReactNode][] = [
  ["queue", "Dashboard", <LayoutDashboard size={18} />],
  ["dossier", "Dossiers", <Search size={18} />],
  ["network", "Réseau", <Building2 size={18} />],
  ["company360", "Historique", <History size={18} />],
  ["notifications", "Notifications", <ClipboardList size={18} />],
  ["advanced", "Avancé", <Database size={18} />],
];
const operatorTabs: [Tab, string, ReactNode][] = [
  ["admin", "Données démo", <Database size={18} />],
];
const status: Record<string, string> = {
  UNRESOLVED: "À clarifier",
  EXPLAINED: "Expliqué",
  INSUFFICIENT: "Information insuffisante",
  NOT_APPLICABLE: "Sans objet",
  PUBLISHED_IN_DEMO: "En attente de réponse",
  RESPONDED: "Réponse reçue",
  NOT_REQUESTED: "Aucune demande",
  PENDING: "En attente",
  ANSWERED: "Répondu",
  AWAITING_HUMAN_REVIEW: "Validation humaine requise",
  ACCEPTED: "Acceptée",
  REJECTED: "Rejetée",
  LIVE: "LIVE",
  TEMPLATE: "Repli déterministe",
  MANUAL: "Manuel",
  NOT_RUN: "Non exécuté",
  ERROR: "Erreur",
  CACHED: "En cache",
  HYPOTHETICAL: "Hypothétique",
  DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY:
    "Origines distinctes · non authentifiées",
  COMMON_ORIGIN: "Origine commune",
  SINGLE_OBSERVATION: "Une observation",
  INVOICE: "Facture",
  ALLOCATION_RESPONSE: "Réponse d’affectation",
  ALLOCATION_REFERENCE: "Référence d’affectation",
  DELIVERY_RECORD: "Bon de livraison",
  PAYMENT_RECORD: "Preuve de règlement",
  CONTRACT: "Contrat",
  DECLARATION: "Déclaration",
  OTHER_OR_UNKNOWN: "Autre / inconnu",
  BUYER_RECEIVED: "Copie reçue par l’acheteur",
  SELLER_ISSUED: "Émission du vendeur",
  INTERNAL_PURCHASE_ENTRY: "Écriture d’achat interne",
  FOLLOW_UP_DUE: "Relance à prévoir",
  ON_TRACK: "Dans la cible de démonstration",
};
const familyLabel: Record<string, string> = {
  COUNTERPARTY: "Concordance des observations",
  SETTLEMENT: "Règlement observé",
  QUANTITY: "Affectation des quantités",
};
const progressLabel: Record<string, string> = {
  UNRESOLVED: "Non expliquée",
  EXPLANATION_RECEIVED: "Réponse reçue",
  EVIDENCE_RECEIVED: "Pièce reçue, analyse en attente",
  EVIDENCE_COHERENT: "Pièce cohérente, validation en attente",
  RESOLVED: "Résolue après décision agent",
};
const confidenceUnit: Record<string, string> = {
  TIMELINESS: "réponses dans les délais",
  ANSWER_COHERENCE: "réponses cohérentes",
  EVIDENCE_CORROBORATION: "pièces corroborées",
  HISTORICAL_STABILITY: "transactions sans conflit répété",
};
const indicator = (value: number | null, state: string) =>
  state === "INSUFFICIENT_DATA" || value === null
    ? "Données insuffisantes"
    : format(value);
const horizonLabel: Record<string, string> = {
  SHORT_HORIZON: "Horizon court",
  LONGER_HORIZON: "Horizon plus long",
  UNKNOWN: "Non précisé",
};
const consistencyLabel: Record<string, string> = {
  CONSISTENT: "Cohérent",
  NEEDS_CLARIFICATION: "Clarification nécessaire",
  INSUFFICIENT: "Informations insuffisantes",
};
const purposeLabel: Record<string, string> = {
  CONSTRUCTION_PROJECT: "Projet de construction",
  RESALE: "Revente",
  OPERATING_USE: "Usage d’exploitation",
  LONG_LIVED_ASSET: "Actif durable",
  OTHER_OR_UNKNOWN: "Autre / à préciser",
};
const contextReasonLabel: Record<string, string> = {
  DECLARED_HORIZON_DATE_CONFLICT:
    "La période déclarée diffère de celle calculée depuis les dates.",
  DECLARED_HORIZON_TEXT_CONFLICT:
    "La période déclarée diffère de celle décrite dans le texte.",
  INTERPRETED_HORIZON_DATE_CONFLICT:
    "La période décrite dans le texte diffère de celle calculée depuis les dates.",
  PURPOSE_CATEGORY_TEXT_CONFLICT:
    "La catégorie d’usage déclarée diffère de celle suggérée par le texte.",
  PROJECT_DATES_MISSING: "Dates de début et de fin non renseignées.",
  INVALID_PROJECT_DATE_ORDER: "La date de fin précède la date de début.",
  LONG_HORIZON_STAGE_MISSING: "Phase du projet non précisée.",
  LONG_HORIZON_BENEFICIARY_MISSING: "Bénéficiaire du projet non précisé.",
  LONG_HORIZON_REFERENCE_MISSING: "Pièce de référence non fournie.",
  CONTEXT_AMBIGUOUS: "Description de l’usage à préciser.",
};
const questionLabel: Record<string, string> = {
  "Q-HORIZON-CONFIRM": "Confirmation de la période prévue",
  "Q-PROJECT-STAGE": "Phase du projet",
  "Q-PROJECT-BENEFICIARY": "Projet, lot ou bénéficiaire",
  "Q-PROJECT-REFERENCE": "Pièce de référence",
  "Q-PROJECT-DATES": "Dates du projet",
  "Q-PURPOSE": "Usage prévu",
};
/** Display labels for server-provided CHOICE values; the value sent is always the enum. */
const choiceLabel: Record<string, string> = {
  SHORT_HORIZON: "Projet à horizon court (90 jours ou moins)",
  LONGER_HORIZON: "Projet à horizon plus long",
  ...purposeLabel,
};
const nodeLabel: Record<string, string> = {
  checks: "Contrôles déterministes",
  retrieval: "Recherche de références publiques",
  router: "Routage des pièces (Jev)",
  context: "Interprétation du contexte",
  reference_note: "Synthèse de références",
  extractor: "Extraction des champs",
  planner: "Planification des questions",
  history: "Signaux historiques (lot B)",
  investigator: "Analyse assistée BOUSSLA",
};
const HORIZON_CONVENTION_FR =
  "Cette catégorie est une convention de démonstration BOUSSLA ; elle ne constitue pas une classification fiscale, comptable ou juridique.";
const scenarioLabel: Record<string, string> = {
  status: "Statut",
  residual_units: "Unités résiduelles",
  unit: "Unité",
};
const format = (value: string | number | null | undefined) =>
  value === null || value === undefined || value === "" ? "N/D" : String(value);
const money = (millimes: number | null) =>
  millimes === null
    ? "N/D"
    : new Intl.NumberFormat("fr-TN", {
        minimumFractionDigits: 3,
        maximumFractionDigits: 3,
      }).format(millimes / 1000) + " TND";
const date = (s: string | null) =>
  s ? new Date(s).toLocaleDateString("fr-FR") : "N/D";
const short = (s: string) => (s.length > 20 ? `${s.slice(0, 16)}…` : s);
/** Animate a new automatic request only the first time its stable ID is seen. */
const seenRequests = new Set<string>();
const firstSeen = (id: string) => {
  if (seenRequests.has(id)) return false;
  seenRequests.add(id);
  return true;
};
const badge = (value: string) => (
  <span
    className={`badge ${["EXPLAINED", "LIVE", "ACCEPTED"].includes(value) ? "good" : ["UNRESOLVED", "PENDING", "PUBLISHED_IN_DEMO", "AWAITING_HUMAN_REVIEW"].includes(value) ? "warn" : ""}`}
  >
    {status[value] || value.replaceAll("_", " ")}
  </span>
);

class ErrorBoundary extends Component<
  { children: ReactNode },
  { crashed: boolean }
> {
  state = { crashed: false };
  static getDerivedStateFromError() {
    return { crashed: true };
  }
  render() {
    return this.state.crashed ? (
      <main className="fatal">
        <h1>Un affichage a échoué.</h1>
        <p>Actualisez la page pour retrouver le dossier.</p>
        <button onClick={() => location.reload()}>Actualiser</button>
      </main>
    ) : (
      this.props.children
    );
  }
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <FolderOpen size={24} />
      <p>{children}</p>
    </div>
  );
}
function Panel({
  title,
  eyebrow,
  children,
  action,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          {eyebrow && <span className="eyebrow">{eyebrow}</span>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
function SectionHead({
  label,
  title,
  detail,
}: {
  label: string;
  title: string;
  detail?: string;
}) {
  return (
    <header className="section-head">
      <span className="eyebrow">{label}</span>
      <h1>{title}</h1>
      {detail && <p>{detail}</p>}
    </header>
  );
}
function Skeleton() {
  return (
    <div className="skeletons">
      <div />
      <div />
      <div />
    </div>
  );
}
function Revision({
  value,
  close,
}: {
  value: RevisionResult;
  close: () => void;
}) {
  const before = value.score_before?.review_index;
  const after = value.score_after?.review_index;
  return (
    <div
      className="revision-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label="Nouvelle révision"
    >
      <div className="revision-card">
        <button
          className="icon-button close"
          aria-label="Fermer"
          onClick={close}
        >
          ×
        </button>
        <span className="eyebrow">Décision enregistrée par le service</span>
        <h2>
          {value.outcome === "ACCEPTED"
            ? "Nouvelle révision créée"
            : "Proposition rejetée"}
        </h2>
        <div className="revision-grid">
          <div>
            <span>Version</span>
            <strong>
              v{value.previous_version} <ArrowRight size={22} /> v
              {value.new_version}
            </strong>
          </div>
          <div>
            <span>Priorité de revue</span>
            <strong>
              {format(before)} <ArrowRight size={22} /> {format(after)}
            </strong>
          </div>
        </div>
        <p className="muted">
          {value.findings_before.find((f) => f.family === "QUANTITY")?.status &&
            status[
              value.findings_before.find((f) => f.family === "QUANTITY")!.status
            ]}{" "}
          →{" "}
          {value.findings_after.find((f) => f.family === "QUANTITY")?.status &&
            status[
              value.findings_after.find((f) => f.family === "QUANTITY")!.status
            ]}
        </p>
        <div className="allocation-flow">
          {value.allocations_before.map((a) => (
            <span key={a.allocation_id}>
              {a.target_project_id} {a.quantity} {a.unit}
            </span>
          ))}{" "}
          <ArrowRight size={18} />{" "}
          {value.allocations_after.map((a) => (
            <span key={a.allocation_id}>
              {a.target_project_id} {a.quantity} {a.unit}
            </span>
          ))}
        </div>
        <p className="success-line">
          <Check size={18} /> Version précédente conservée dans l’historique
        </p>
        <button className="primary" onClick={close}>
          Continuer la revue
        </button>
      </div>
    </div>
  );
}

function AppInner() {
  const query = useQueryClient();
  const [booting, setBooting] = useState(shouldShowBoot);
  const endBoot = useCallback(() => setBooting(false), []);
  const [role, setRole] = useState<Role>("OFFICER");
  const [tab, setTab] = useState<Tab>("queue");
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState<RevisionResult | null>(null);
  const locked = useRef(false);
  const bootstrap = useQuery({
    queryKey: ["bootstrap", role],
    queryFn: () => api.bootstrap(role),
  });
  const caseId =
    selectedCaseId && bootstrap.data?.case_ids.includes(selectedCaseId)
      ? selectedCaseId
      : bootstrap.data?.case_ids[0];
  const caseQuery = useQuery({
    queryKey: ["case", role, caseId],
    queryFn: () => api.case(role, caseId!),
    enabled: !!caseId,
  });
  const current = caseQuery.data;
  const switchRole = (next: Role) => {
    if (next === role) return;
    setRole(next);
    setTab(
      next === "COMPANY" ? "overview" : next === "OPERATOR" ? "admin" : "queue",
    );
    setSelectedCaseId(null);
    setNotice("");
    setRevision(null);
    query.removeQueries({ queryKey: ["case"] });
    query.removeQueries({ queryKey: ["history"] });
    query.removeQueries({ queryKey: ["notifications"] });
    query.removeQueries({ queryKey: ["network"] });
    query.removeQueries({ queryKey: ["queue"] });
    query.removeQueries({ queryKey: ["admin"] });
  };
  const refresh = async () => {
    await query.invalidateQueries();
    setNotice("Données actualisées.");
  };
  const act = async (job: () => Promise<unknown>, success: string) => {
    if (locked.current) return;
    locked.current = true;
    try {
      const value = await job();
      if (value && typeof value === "object" && "previous_version" in value)
        setRevision(value as RevisionResult);
      setNotice(success);
      await query.invalidateQueries({ queryKey: ["case"] });
      await query.invalidateQueries({ queryKey: ["queue"] });
      await query.invalidateQueries({ queryKey: ["history"] });
      await query.invalidateQueries({ queryKey: ["audit"] });
      await query.invalidateQueries({ queryKey: ["notifications"] });
      await query.invalidateQueries({ queryKey: ["network"] });
      return value;
    } catch (error) {
      if (error instanceof ApiError && error.code === "STALE_REVISION") {
        setNotice("Le dossier a changé. Les données ont été actualisées.");
        await query.invalidateQueries({ queryKey: ["case"] });
      } else
        setNotice(
          error instanceof Error ? error.message : "Action impossible.",
        );
      throw error;
    } finally {
      locked.current = false;
    }
  };
  const tabs =
    role === "COMPANY"
      ? companyTabs
      : role === "OPERATOR"
        ? operatorTabs
        : officerTabs;
  return (
    <div className="app-shell">
      {booting && <BootSplash onDone={endBoot} />}
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <BousslaMark size={32} />
          </span>
          <span>
            BOUSSLA<small>Espace de revue</small>
          </span>
        </div>
        <div className="workspace-label">
          ESPACE{" "}
          {role === "COMPANY"
            ? "ENTREPRISE"
            : role === "OPERATOR"
              ? "OPÉRATEUR DÉMO"
              : "AGENT"}
        </div>
        <nav aria-label="Navigation principale">
          {tabs.map(([id, label, icon]) => (
            <button
              key={id}
              className={`nav-item ${tab === id ? "selected" : ""}`}
              onClick={() => setTab(id)}
            >
              {icon}
              <span>{label}</span>
              {tab === id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="demo-pill">DONNÉES SYNTHÉTIQUES</span>
          <p>
            Simulation locale de rôles — pas une authentification de production.
          </p>
          <div className="system">
            <span className="live-dot" /> Service local{" "}
            <span>{current?.mode || "—"}</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <span>Workspace</span>
            <ChevronRight size={15} />
            <strong>{caseId || "Dossier"}</strong>
            {current && (
              <span className="version">v{current.case_version}</span>
            )}
          </div>
          <div className="top-actions">
            {current && badge(current.mode)}
            <div
              className="role-switch"
              role="group"
              aria-label="Rôle de démonstration"
            >
              <button
                className={role === "COMPANY" ? "active" : ""}
                onClick={() => switchRole("COMPANY")}
              >
                Entreprise
              </button>
              <button
                className={role === "OFFICER" ? "active" : ""}
                onClick={() => switchRole("OFFICER")}
              >
                Agent
              </button>
              <button
                className={role === "OPERATOR" ? "active" : ""}
                onClick={() => switchRole("OPERATOR")}
                title="Administration de données synthétiques — démonstration locale."
              >
                Opérateur démo
              </button>
            </div>
            <button
              className="icon-button"
              onClick={refresh}
              aria-label="Actualiser"
              title="Actualiser"
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>
        <main className="content">
          {notice && (
            <div className="toast" role="status">
              <span>{notice}</span>
              <button
                aria-label="Fermer le message"
                onClick={() => setNotice("")}
              >
                ×
              </button>
            </div>
          )}
          {role === "OPERATOR" ? (
            bootstrap.isLoading ? (
              <Skeleton />
            ) : (
              <DemoAdmin enabled={!!bootstrap.data?.demo_admin?.can_list} />
            )
          ) : bootstrap.isLoading || caseQuery.isLoading ? (
            <Skeleton />
          ) : bootstrap.isError || caseQuery.isError ? (
            <div className="error-state">
              <h1>Le dossier ne peut pas être chargé</h1>
              <p>{(bootstrap.error || caseQuery.error)?.message}</p>
              <button className="primary" onClick={refresh}>
                Réessayer
              </button>
            </div>
          ) : !current ? (
            <Empty>Aucun dossier accessible pour ce rôle.</Empty>
          ) : current.audience === "COMPANY" ? (
            <Company caseView={current} tab={tab} act={act} setTab={setTab} />
          ) : (
            <Officer
              caseView={current}
              tab={tab}
              act={act}
              setTab={setTab}
              onSelectCase={(id) => {
                if (!bootstrap.data?.case_ids.includes(id)) {
                  setNotice("Ce dossier n’est pas assigné à ce rôle.");
                  return;
                }
                setSelectedCaseId(id);
                setTab("dossier");
              }}
            />
          )}
        </main>
      </div>
      {revision && (
        <Revision value={revision} close={() => setRevision(null)} />
      )}
    </div>
  );
}

const networkSignalLabels: Record<string, string> = {
  SUPPLIER_CONCENTRATION: "Concentration fournisseur",
  REPEATED_AMOUNT: "Montants répétés",
  RECIPROCAL_LINK: "Échanges réciproques",
};

function NetworkOverview({ c }: { c: OfficerCaseView }) {
  const [scope, setScope] = useState<"case" | "all">("case");
  const graph = useQuery({
    queryKey: ["network", "OFFICER", scope, c.case_id],
    queryFn: () =>
      scope === "case" ? api.networkCase(c.case_id) : api.network(),
  });
  const nodes = new Map(
    graph.data?.nodes.map((node) => [node.node_id, node]) ?? [],
  );
  const companyLinks =
    graph.data?.edges.filter((edge) => edge.kind === "SELLS_TO") ?? [];
  return (
    <>
      <SectionHead
        label="RELATIONS DOCUMENTÉES"
        title="Réseau"
        detail="Relations issues des dossiers assignés à l’agent, avec leurs sources."
      />
      <label className="network-scope">
        Périmètre du réseau
        <select
          value={scope}
          onChange={(event) => setScope(event.target.value as "case" | "all")}
        >
          <option value="case">Dossier courant · {c.case_id}</option>
          <option value="all">Tous les dossiers assignés</option>
        </select>
      </label>
      {graph.isLoading ? (
        <Skeleton />
      ) : graph.isError ? (
        <p role="alert">Réseau indisponible.</p>
      ) : (
        <>
          <div className="metric-grid four">
            <div className="metric">
              <span>Entreprises</span>
              <strong>
                {graph.data?.nodes.filter((node) => node.kind === "COMPANY")
                  .length ?? 0}
              </strong>
            </div>
            <div className="metric">
              <span>Factures observées</span>
              <strong>
                {graph.data?.nodes.filter((node) => node.kind === "INVOICE")
                  .length ?? 0}
              </strong>
            </div>
            <div className="metric">
              <span>Paiements enregistrés</span>
              <strong>
                {graph.data?.nodes.filter((node) => node.kind === "PAYMENT")
                  .length ?? 0}
              </strong>
            </div>
            <div className="metric">
              <span>Relations sourcées</span>
              <strong>{graph.data?.edges.length ?? 0}</strong>
            </div>
          </div>
          {graph.data && <NetworkGraph3D graph={graph.data} dossier={c} />}
          <Panel
            title="Signaux réseau à examiner"
            eyebrow="DESCRIPTIF · SOURCÉ"
          >
            {graph.data?.signals.length ? (
              graph.data.signals.map((signal) => (
                <article className="document" key={signal.signal_id}>
                  <strong>
                    {networkSignalLabels[signal.kind] ?? "Signal réseau"}
                  </strong>
                  <p>{signal.explanation_fr}</p>
                  <small>
                    {signal.sample_size} transaction(s) dans l’échantillon ·
                    Sources : {signal.source_ids.join(", ")}
                  </small>
                </article>
              ))
            ) : (
              <p>Aucun motif réseau établi sur les transactions visibles.</p>
            )}
            <p className="footnote">
              Les dossiers visibles ne constituent pas une couverture exhaustive
              du réseau. Aucun signal ne modifie l’indice de revue ni ne conclut
              à une fraude.
            </p>
          </Panel>
          <Panel
            title="Relations entre entreprises"
            eyebrow="ACHETEUR · VENDEUR"
          >
            {companyLinks.length ? (
              companyLinks.map((edge) => (
                <article className="document" key={edge.edge_id}>
                  <strong>
                    {nodes.get(edge.source)?.label ?? edge.source} →{" "}
                    {nodes.get(edge.target)?.label ?? edge.target}
                  </strong>
                  <p>
                    Dossier {edge.case_id} · {edge.source_ids.length}{" "}
                    transaction(s) enregistrée(s)
                  </p>
                  <small>
                    Sources : {edge.source_ids.join(", ")} ·{" "}
                    {edge.provenance_status}
                  </small>
                </article>
              ))
            ) : (
              <p>Aucune relation acheteur-vendeur établie dans ce périmètre.</p>
            )}
            <p className="footnote">{graph.data?.note_fr}</p>
          </Panel>
          <details className="dossier-secondary">
            <summary>Explorer les nœuds du dossier {c.case_id}</summary>
            {graph.data?.nodes
              .filter((node) => node.case_ids.includes(c.case_id))
              .map((node) => (
                <article className="document" key={node.node_id}>
                  <strong>
                    {node.kind} · {node.label}
                  </strong>
                  <small>{node.node_id}</small>
                </article>
              ))}
          </details>
        </>
      )}
    </>
  );
}

function ActionNotifications({ c }: { c: OfficerCaseView }) {
  return (
    <>
      <SectionHead
        label="À TRAITER"
        title="Notifications"
        detail="Actions internes dérivées du dossier en cours."
      />
      <NotificationFeed role="OFFICER" caseId={c.case_id} />
      <Panel title="Priorités de revue">
        {c.recommended_actions?.length ? (
          c.recommended_actions.map((action) => (
            <article className="document" key={action.action_id}>
              <strong>{action.title_fr}</strong>
              <p>{action.reason}</p>
              <small>
                Priorité {action.priority} · {action.status}
              </small>
            </article>
          ))
        ) : (
          <p>Aucune action interne à signaler.</p>
        )}
      </Panel>
    </>
  );
}

function NotificationFeed({ role, caseId }: { role: Role; caseId: string }) {
  const queryClient = useQueryClient();
  const [readError, setReadError] = useState<string | null>(null);
  const feed = useQuery({
    queryKey: ["notifications", role, caseId],
    queryFn: () => api.notifications(role, caseId),
  });
  return (
    <Panel eyebrow="ÉVÉNEMENTS DU DOSSIER" title="Mises à jour internes">
      {feed.isLoading ? (
        <p>Chargement des mises à jour…</p>
      ) : feed.isError ? (
        <p role="alert">Mises à jour indisponibles.</p>
      ) : feed.data?.items.length ? (
        feed.data.items.map((item) => (
          <article className="document" key={item.notification_id}>
            <strong>{item.title_fr}</strong>
            <p>{item.message_fr}</p>
            {item.status === "CURRENT_SIGNAL" ? (
              <small>Signal courant · à réévaluer</small>
            ) : item.read_at ? (
              <small>
                Lu le {new Date(item.read_at).toLocaleString("fr-FR")}
              </small>
            ) : (
              <button
                type="button"
                onClick={async () => {
                  try {
                    setReadError(null);
                    await api.markNotificationRead(
                      role,
                      caseId,
                      item.notification_id,
                    );
                    await queryClient.invalidateQueries({
                      queryKey: ["notifications", role, caseId],
                    });
                  } catch (error) {
                    setReadError(
                      error instanceof Error
                        ? error.message
                        : "Lecture non enregistrée.",
                    );
                  }
                }}
              >
                Marquer comme lu
              </button>
            )}
            {!!item.source_ids?.length && (
              <small>Sources : {item.source_ids.join(", ")}</small>
            )}
            <small>
              {new Date(item.occurred_at).toLocaleString("fr-FR", {
                dateStyle: "short",
                timeStyle: "short",
              })}{" "}
              · v{item.case_version}
            </small>
          </article>
        ))
      ) : (
        <p>Aucune mise à jour à signaler.</p>
      )}
      {readError && <p role="alert">{readError}</p>}
    </Panel>
  );
}

function Company({
  caseView: c,
  tab,
  act,
  setTab,
}: {
  caseView: CompanyCaseView;
  tab: Tab;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
  setTab: (tab: Tab) => void;
}) {
  if (tab === "overview")
    return (
      <>
        <SectionHead
          label="ESPACE ENTREPRISE"
          title="Votre dossier, en un regard"
          detail={`${c.company_display_name} · ${c.case_id}`}
        />
        <div className="metric-grid four">
          <div className="metric">
            <span>Dossier</span>
            <strong className="mono small">{c.case_id}</strong>
            <small>Suivi local</small>
          </div>
          <div className="metric">
            <span>Version</span>
            <strong>v{c.case_version}</strong>
            <small>Historique conservé</small>
          </div>
          <div className="metric">
            <span>Pièces visibles</span>
            <strong>{c.documents.length}</strong>
            <small>Origine tracée</small>
          </div>
          <div className="metric">
            <span>Demandes ouvertes</span>
            <strong>
              {
                c.inbox.filter((r) => r.request.status === "PUBLISHED_IN_DEMO")
                  .length
              }
            </strong>
            <small>Boîte de démonstration</small>
          </div>
        </div>
        <details>
          <summary>Déclarer ou modifier le contexte</summary>
          <ContextAssessment ctx={c.context_assessment} />
          <ContextForm c={c} act={act} />
        </details>
        <div className="two-col">
          <Operations c={c} compact />
          <Panel eyebrow="VOTRE SITUATION" title="Actions à poursuivre">
            {c.inbox
              .filter((item) => item.request.status === "PUBLISHED_IN_DEMO")
              .map((item) => (
                <div className="next-step" key={item.request.request_id}>
                  <span className="step-num">!</span>
                  <div>
                    <strong>Justification requise</strong>
                    <p>{item.text_fr}</p>
                    <button
                      className="secondary"
                      onClick={() => setTab("requests")}
                    >
                      Voir la demande
                    </button>
                  </div>
                </div>
              ))}
            {c.context_claims.length === 0 && (
              <div className="next-step">
                <span className="step-num">1</span>
                <div>
                  <strong>Renseigner le contexte</strong>
                  <p>Précisez l’usage prévu, le projet et le bénéficiaire.</p>
                  <button
                    className="secondary"
                    onClick={() => setTab("messages")}
                  >
                    Déclarer le contexte
                  </button>
                </div>
              </div>
            )}
            {c.documents.some(
              (document) =>
                document.processing_status === "ANALYZED_AWAITING_REVIEW",
            ) && (
              <p className="footnote">
                Analyse automatique terminée. En attente de validation par
                l’agent.
              </p>
            )}
            {c.inbox.every(
              (item) => item.request.status !== "PUBLISHED_IN_DEMO",
            ) &&
              c.context_claims.length > 0 && (
                <p>Aucune réponse requise actuellement.</p>
              )}
          </Panel>
        </div>
      </>
    );
  if (tab === "operations")
    return (
      <>
        <SectionHead
          label="TRAÇABILITÉ"
          title="Opérations observées"
          detail="Les montants facturés, réglés et déclarés sont présentés séparément."
        />
        <Operations c={c} />
      </>
    );
  if (tab === "messages")
    return (
      <>
        <SectionHead
          label="DÉCLARATION"
          title="Messages et contexte"
          detail="Contexte déclaré par l’entreprise — il ne constitue pas à lui seul une preuve."
        />
        {c.inbox.map((item) => (
          <article className="document" key={item.request.request_id}>
            <strong>Demande {item.request.request_id}</strong>
            <p>{item.text_fr}</p>
          </article>
        ))}
        <NotificationFeed role="COMPANY" caseId={c.case_id} />
        {c.responses.map((response) => (
          <article className="document" key={response.response_id}>
            <strong>Réponse {response.response_id}</strong>
            <p>
              {Object.values(response.answers).join(" · ") ||
                "Pièce ou répartition transmise"}
            </p>
          </article>
        ))}
        <details>
          <summary>Contexte déclaré</summary>
          <ContextAssessment ctx={c.context_assessment} />
          <ContextForm c={c} act={act} />
        </details>
      </>
    );
  if (tab === "requests")
    return (
      <>
        <SectionHead
          label="ÉCHANGES"
          title="Demandes de précision"
          detail="Les demandes disponibles pour ce dossier apparaissent ici."
        />
        <RequestInbox c={c} act={act} />
      </>
    );
  return (
    <>
      <SectionHead
        label="PIÈCES"
        title="Documents du dossier"
        detail="Chaque document conserve son origine et son empreinte."
      />
      <Upload c={c} act={act} />
      {c.documents
        .filter(
          (d) =>
            d.extraction?.status === "PROPOSED" &&
            d.extraction.proposal_id &&
            d.extraction.candidates?.length,
        )
        .map((d) => (
          <TranscriptionForm
            key={`${d.document.document_id}:${c.case_version}`}
            c={c}
            document={d}
            act={act}
          />
        ))}
      <Documents c={c} />
    </>
  );
}

function Operations({
  c,
  compact = false,
}: {
  c: CompanyCaseView | OfficerCaseView;
  compact?: boolean;
}) {
  return (
    <Panel
      eyebrow="FLUX DISTINCTS"
      title={compact ? "Dernières opérations" : "Factures et règlements"}
    >
      <div className="table-wrap">
        <table className={compact ? "compact-table" : ""}>
          <thead>
            <tr>
              <th>Facture</th>
              <th>Date</th>
              <th>Contrepartie</th>
              <th>Facturé</th>
              <th>Réglé observé</th>
              <th>Déclaré</th>
              <th>Origine</th>
            </tr>
          </thead>
          <tbody>
            {c.transactions.map((t) => (
              <tr key={t.transaction_id}>
                <td className="mono">{format(t.invoice_number)}</td>
                <td>{date(t.issued_on)}</td>
                <td>{format(t.counterparty_display_name)}</td>
                <td>{money(t.invoiced_gross_millimes)}</td>
                <td>{money(t.settled_millimes)}</td>
                <td>{money(t.declared_millimes)}</td>
                <td>{badge(t.corroboration_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!c.transactions.length && <Empty>Aucune opération disponible.</Empty>}
      <p className="footnote">
        Un montant facturé ne prouve pas un règlement. Les trois colonnes ne
        forment pas un total.
      </p>
    </Panel>
  );
}

function ContextAssessment({ ctx }: { ctx: ContextAssessmentView | null }) {
  if (!ctx)
    return (
      <Panel
        eyebrow="COHÉRENCE DU CONTEXTE"
        title="Déclaré · Interprété · Calculé"
      >
        <Empty>Aucune déclaration de contexte à comparer.</Empty>
      </Panel>
    );
  const interpreted =
    ctx.interpretation_mode === "LIVE"
      ? horizonLabel[ctx.interpreted_horizon]
      : "Non disponible";
  return (
    <Panel
      eyebrow="COHÉRENCE DU CONTEXTE"
      title="Déclaré · Interprété · Calculé"
    >
      <div className="metric-grid four context-grid">
        <div className="metric">
          <span>Déclaré</span>
          <strong className="small">
            {horizonLabel[ctx.declared_horizon]}
          </strong>
          <small>
            {purposeLabel[ctx.declared_purpose_category] ||
              ctx.declared_purpose_category}
          </small>
        </div>
        <div className="metric">
          <span>Interprété par IA</span>
          <strong className="small">{interpreted}</strong>
          <small>
            {ctx.interpretation_mode === "LIVE"
              ? purposeLabel[ctx.interpreted_purpose_category] ||
                ctx.interpreted_purpose_category
              : status[ctx.interpretation_mode] || ctx.interpretation_mode}
          </small>
        </div>
        <div className="metric">
          <span>Calculé depuis les dates</span>
          <strong className="small">
            {ctx.duration_days === null
              ? "Dates non renseignées"
              : `${ctx.duration_days} jours · ${horizonLabel[ctx.calculated_horizon]}`}
          </strong>
          <small>Calcul déterministe</small>
        </div>
        <div className="metric">
          <span>Cohérence</span>
          <strong className="small">
            {consistencyLabel[ctx.consistency_status]}
          </strong>
          <small>Corroboration : non évaluée</small>
        </div>
      </div>
      {ctx.reason_codes.length > 0 && (
        <ul className="context-reasons">
          {ctx.reason_codes.map((code) => (
            <li key={code}>
              {contextReasonLabel[code] || "Élément à préciser."}
            </li>
          ))}
        </ul>
      )}
      {ctx.supporting_spans.length > 0 && (
        <div className="tags">
          {ctx.supporting_spans.map((span) => (
            <span className="badge" key={span}>
              « {span} »
            </span>
          ))}
        </div>
      )}
      {ctx.recommended_question_ids.length > 0 && (
        <p className="muted">
          Précisions utiles :{" "}
          {ctx.recommended_question_ids
            .map((id) => questionLabel[id] || id)
            .join(" · ")}
        </p>
      )}
      <p className="footnote">
        Cette comparaison contextuelle n’affecte pas automatiquement la priorité
        de revue. {ctx.horizon_convention_fr}
      </p>
    </Panel>
  );
}

function ContextForm({
  c,
  act,
}: {
  c: CompanyCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [pending, setPending] = useState(false);
  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (pending) return;
    setPending(true);
    const data = new FormData(e.currentTarget);
    const context: Record<string, FormDataEntryValue | null> =
      Object.fromEntries([...data].filter(([, value]) => value !== ""));
    if (
      data.get("project_id") === "__GENERAL__" &&
      c.capabilities?.supports_null_project_id
    )
      context.project_id = null;
    try {
      await act(
        () => api.context(c.case_id, c.case_version, context),
        "Contexte déclaré et nouvelle version créée.",
      );
    } catch {
      /* Notice shown by App */
    } finally {
      setPending(false);
    }
  };
  return (
    <div className="two-col form-layout">
      <Panel eyebrow="NOUVELLE DÉCLARATION" title="Usage prévu">
        <form onSubmit={submit} className="form-grid">
          <label>
            Projet concerné
            <select name="project_id" required>
              {c.projects.map((p) => (
                <option key={p.project_id} value={p.project_id}>
                  {p.label}
                </option>
              ))}
              {c.capabilities?.supports_null_project_id && (
                <option value="__GENERAL__">
                  Aucun projet / usage général de l’entreprise
                </option>
              )}
            </select>
          </label>
          <label>
            Catégorie d’usage
            <select name="purpose_category">
              <option value="CONSTRUCTION_PROJECT">
                Projet de construction
              </option>
              <option value="RESALE">Revente</option>
              <option value="OPERATING_USE">Usage d’exploitation</option>
              <option value="LONG_LIVED_ASSET">
                Actif durable (ex. achat de véhicule)
              </option>
              <option value="OTHER_OR_UNKNOWN">Autre / à préciser</option>
            </select>
          </label>
          <label>
            Horizon du projet (déclaré)
            <select name="declared_horizon" defaultValue="">
              <option value="">Non précisé</option>
              <option value="SHORT_HORIZON">Projet à horizon court</option>
              <option value="LONGER_HORIZON">Projet à horizon plus long</option>
            </select>
            <small className="field-help">{HORIZON_CONVENTION_FR}</small>
          </label>
          <label className="wide">
            Usage prévu
            <textarea
              name="purpose_text"
              rows={3}
              maxLength={2000}
              placeholder="Décrivez l’affectation prévue…"
              required
            />
          </label>
          <label>
            Bénéficiaire
            <input
              name="beneficiary_type"
              placeholder="Ex. projet P1"
              required
            />
          </label>
          <label>
            Phase
            <input name="stage" placeholder="Ex. gros œuvre" />
          </label>
          <label>
            Début prévu
            <input name="planned_start" type="date" />
          </label>
          <label>
            Fin prévue
            <input name="planned_end" type="date" />
          </label>
          <button
            className="primary wide"
            disabled={
              pending ||
              (!c.projects.length && !c.capabilities?.supports_null_project_id)
            }
          >
            {pending ? "Enregistrement…" : "Enregistrer la déclaration"}
          </button>
        </form>
      </Panel>
      <Panel eyebrow="DÉCLARATIONS EXISTANTES" title="Contexte enregistré">
        {c.context_claims.length ? (
          <div className="stack">
            {c.context_claims.map((claim) => (
              <div className="record" key={claim.claim_id}>
                <div className="record-top">
                  {badge(claim.purpose_category)}
                  <span>{date(claim.submitted_at)}</span>
                </div>
                <strong>{claim.purpose_text}</strong>
                <p>
                  {claim.beneficiary_type} · {format(claim.stage)} ·{" "}
                  {horizonLabel[claim.declared_horizon] || "Non précisé"}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <Empty>Aucun contexte déclaré.</Empty>
        )}
      </Panel>
    </div>
  );
}

function Upload({
  c,
  act,
}: {
  c: CompanyCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const choose = (f?: File) => {
    if (!f) return;
    setError(
      f.type !== "application/pdf" || !f.name.toLowerCase().endsWith(".pdf")
        ? "Seuls les PDF sont acceptés."
        : f.size > 10 * 1024 * 1024
          ? "Taille maximale : 10 Mo."
          : "",
    );
    setFile(f);
  };
  const send = async () => {
    if (!file || error || pending) return;
    setPending(true);
    try {
      await act(
        () => api.upload("COMPANY", c.case_id, file, c.case_version),
        "Pièce déposée dans le dossier.",
      );
      setFile(null);
    } catch {
      /* Notice shown by App */
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel eyebrow="AJOUTER UNE PIÈCE" title="Déposer un justificatif">
      <div
        className="dropzone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          choose(e.dataTransfer.files[0]);
        }}
      >
        <UploadCloud size={32} />
        <strong>Déposer une facture ou pièce justificative</strong>
        <p>PDF uniquement · 10 Mo maximum</p>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          onChange={(e) => choose(e.target.files?.[0])}
          aria-label="Choisir un PDF"
        />
        <button className="secondary" onClick={() => input.current?.click()}>
          Choisir un fichier
        </button>
      </div>
      {file && (
        <div className="upload-ready">
          <span>
            {file.name} · {(file.size / 1024 / 1024).toFixed(2)} Mo
          </span>
          <button
            className="primary"
            disabled={!!error || pending}
            onClick={send}
          >
            {pending ? "Dépôt en cours…" : "Confirmer le dépôt"}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="error-text">
          {error}
        </p>
      )}
    </Panel>
  );
}

function Documents({ c }: { c: CompanyCaseView | OfficerCaseView }) {
  return (
    <Panel eyebrow="PROVENANCE" title="Pièces enregistrées">
      {c.documents.length ? (
        <div className="document-grid">
          {c.documents.map((d) => (
            <article className="document" key={d.document.document_id}>
              <div className="document-icon">
                <FileText size={22} />
              </div>
              <div>
                <strong>{d.document.original_filename}</strong>
                <p className="mono">{d.document.document_id}</p>
                <div className="tags">
                  {badge(d.routing?.candidate_class || "Classe inconnue")}
                  {badge(d.routing?.mode || "NOT_RUN")}
                </div>
                <dl>
                  <div>
                    <dt>Origine</dt>
                    <dd>
                      {d.document.acquisition_channel.replaceAll("_", " ")}
                    </dd>
                  </div>
                  {d.document.origin_group_id && (
                    <div>
                      <dt>Groupe d’origine</dt>
                      <dd>{d.document.origin_group_id}</dd>
                    </div>
                  )}
                  <div>
                    <dt>SHA-256</dt>
                    <dd className="mono">{short(d.document.sha256)}</dd>
                  </div>
                  <div>
                    <dt>Extraction</dt>
                    <dd>{d.extraction?.status || "N/D"}</dd>
                  </div>
                </dl>
                {d.processing_status === "ANALYZED_AWAITING_REVIEW" && (
                  <p>Analyse automatique terminée. En attente de validation.</p>
                )}
                {d.analysis && (
                  <details>
                    <summary>Analyse documentaire</summary>
                    {d.analysis.confidence && (
                      <div>
                        <strong>
                          Confiance documentaire :{" "}
                          {{
                            HIGH: "élevée",
                            MEDIUM: "moyenne",
                            LOW: "faible",
                            INSUFFICIENT_DATA: "données insuffisantes",
                          }[d.analysis.confidence.level] ?? "inconnue"}
                        </strong>
                        <p>
                          {d.analysis.confidence.value === null
                            ? "Indice non calculable"
                            : `${d.analysis.confidence.value}/100`}{" "}
                          · {d.analysis.confidence.measured_dimensions}/4
                          dimensions mesurées
                        </p>
                        {d.analysis.confidence.factors.map((factor) => (
                          <p key={factor.code}>
                            {factor.code} : {factor.value ?? "inconnu"} ·{" "}
                            {factor.explanation_fr}
                          </p>
                        ))}
                        <small>{d.analysis.confidence.explanation_fr}</small>
                      </div>
                    )}
                    <p>
                      {d.analysis.classification} ·{" "}
                      {d.analysis.authenticity_statement}
                    </p>
                    <small>
                      {d.analysis.rule_version} · {d.analysis.calculated_at}
                    </small>
                    {d.analysis.checks.map((check) => (
                      <p key={check.code}>
                        <strong>{check.status}</strong> · {check.explanation_fr}
                        <br />
                        <small>{check.source_ids.join(", ")}</small>
                      </p>
                    ))}
                    <p>
                      Causes proposées :{" "}
                      {d.analysis.linked_cause_ids.join(", ") ||
                        "Aucun lien établi"}
                    </p>
                  </details>
                )}
                {d.integrity?.limitations?.length ? (
                  <small>Limites : {d.integrity.limitations.join(", ")}</small>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <Empty>Aucune pièce visible.</Empty>
      )}
    </Panel>
  );
}

function RequestInbox({
  c,
  act,
}: {
  c: CompanyCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  return (
    <div className="stack">
      {c.inbox.length ? (
        c.inbox.map((r) => (
          <AutoRequestFrame key={r.request.request_id} request={r}>
            <Panel
              eyebrow={`DEMANDE ${r.request.request_id}`}
              title="Précisions attendues"
              action={badge(r.request.status)}
            >
              <p className="muted">
                Publiée le {date(r.request.published_at)} · Pièces attendues :{" "}
                {r.request.allowed_document_types
                  .map((kind) => status[kind] || kind)
                  .join(", ") || "à préciser"}
              </p>
              <RequestMeta request={r} />
              <p>{r.text_fr}</p>
              <ul className="question-list staggered">
                {r.questions.map((q, i) => (
                  <li
                    key={q.question_id}
                    style={{ animationDelay: `${120 + i * 80}ms` }}
                  >
                    {q.text_fr}
                  </li>
                ))}
              </ul>
              {r.request.status === "PUBLISHED_IN_DEMO" &&
                (selected === r.request.request_id ? (
                  <ResponseComposer c={c} request={r} act={act} />
                ) : (
                  <button
                    className="primary"
                    onClick={() => setSelected(r.request.request_id)}
                  >
                    Répondre à la demande <ArrowRight size={16} />
                  </button>
                ))}
              {r.request.status === "RESPONDED" &&
                c.responses
                  .filter(
                    (response) => response.request_id === r.request.request_id,
                  )
                  .map((response) => (
                    <LateDocumentLink
                      key={response.response_id}
                      c={c}
                      response={response}
                      act={act}
                    />
                  ))}
              <p className="footnote">Déclaration seule ≠ preuve acceptée.</p>
            </Panel>
          </AutoRequestFrame>
        ))
      ) : (
        <Empty>Aucune demande publiée pour ce dossier.</Empty>
      )}
    </div>
  );
}

function LateDocumentLink({
  c,
  response,
  act,
}: {
  c: CompanyCaseView;
  response: CompanyCaseView["responses"][number];
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [documentId, setDocumentId] = useState("");
  const available = c.documents.filter(
    (entry) =>
      entry.document.acquisition_channel === "COMPANY_UPLOAD" &&
      !response.document_ids.includes(entry.document.document_id),
  );
  if (!available.length) return null;
  return (
    <div className="response-form">
      <label>
        Pièce déjà déposée pour cette réponse
        <select
          value={documentId}
          onChange={(e) => setDocumentId(e.target.value)}
        >
          <option value="">Choisir une pièce…</option>
          {available.map((entry) => (
            <option
              key={entry.document.document_id}
              value={entry.document.document_id}
            >
              {entry.document.original_filename}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="secondary"
        disabled={!documentId}
        onClick={() =>
          void act(
            () =>
              api.attachDocument(
                c.case_id,
                response.response_id,
                c.case_version,
                documentId,
              ),
            "Pièce liée à la réponse. Analyse du dossier actualisée.",
          )
        }
      >
        Lier cette pièce
      </button>
    </div>
  );
}

/** One-time entrance for a NEW automatic request (stable ID; never replays on rerender). */
function AutoRequestFrame({
  request,
  children,
}: {
  request: RequestView;
  children: ReactNode;
}) {
  const [animate] = useState(
    () =>
      request.request.origin === "AUTOMATIC" &&
      firstSeen(request.request.request_id),
  );
  return (
    <div className={animate ? "auto-request-enter" : undefined}>{children}</div>
  );
}

/** Origin, reason, demo target and follow-up state exactly as supplied by the service. */
function RequestMeta({ request: r }: { request: RequestView }) {
  return (
    <>
      {r.request.origin === "AUTOMATIC" && (
        <div className="auto-request-banner">
          <span className="auto-badge">Demande automatique BOUSSLA</span>
          <span>
            Précisions demandées automatiquement à partir des informations
            disponibles.
          </span>
        </div>
      )}
      {r.request.target_response_at && (
        <p className="muted">
          Cible de réponse de démonstration :{" "}
          {date(r.request.target_response_at)}
          {r.request.overdue_state === "FOLLOW_UP_DUE" && (
            <span className="badge warn follow-up">Relance à prévoir</span>
          )}
        </p>
      )}
    </>
  );
}

function ResponseComposer({
  c,
  request,
  act,
}: {
  c: CompanyCaseView;
  request: RequestView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [doc, setDoc] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const attachmentInput = useRef<HTMLInputElement>(null);
  const [uploadPending, setUploadPending] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [quantityOne, setQuantityOne] = useState("");
  const [quantityTwo, setQuantityTwo] = useState("");
  const [projectOne, setProjectOne] = useState(c.projects[0]?.project_id || "");
  const [projectTwo, setProjectTwo] = useState(c.projects[1]?.project_id || "");
  const targets = Array.from(
    new Map(
      c.allocations.map((allocation) => [
        `${allocation.transaction_id}:${allocation.line_id}`,
        {
          transaction_id: allocation.transaction_id,
          line_id: allocation.line_id,
        },
      ]),
    ).values(),
  );
  const [targetIndex, setTargetIndex] = useState(0);
  const [allocationError, setAllocationError] = useState("");
  const [pending, setPending] = useState(false);
  const uploadAttachment = async () => {
    if (!attachment || uploadPending) return;
    setUploadError("");
    if (
      attachment.type !== "application/pdf" ||
      !attachment.name.toLowerCase().endsWith(".pdf") ||
      attachment.size > 10 * 1024 * 1024
    ) {
      setUploadError("Pièce PDF requise, 10 Mo maximum.");
      return;
    }
    setUploadPending(true);
    try {
      const uploaded = (await act(
        () => api.upload("COMPANY", c.case_id, attachment, c.case_version),
        "Pièce déposée ; elle est prête à être jointe à la réponse.",
      )) as DocumentView;
      setDoc(uploaded.document.document_id);
      setAttachment(null);
      if (attachmentInput.current) attachmentInput.current.value = "";
    } catch {
      /* Notice shown by App */
    } finally {
      setUploadPending(false);
    }
  };
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (pending) return;
    if (
      (quantityOne || quantityTwo) &&
      (!quantityOne ||
        !quantityTwo ||
        !targets[targetIndex] ||
        projectOne === projectTwo)
    ) {
      setAllocationError(
        "Choisissez deux projets distincts, une ligne et les deux quantités.",
      );
      return;
    }
    setAllocationError("");
    setPending(true);
    const allocation =
      quantityOne && quantityTwo && targets[targetIndex]
        ? {
            transaction_id: targets[targetIndex].transaction_id,
            line_id: targets[targetIndex].line_id,
            splits: {
              [projectOne]: quantityOne,
              [projectTwo]: quantityTwo,
            },
          }
        : undefined;
    try {
      await act(
        () =>
          api.respond(c.case_id, request.request.request_id, c.case_version, {
            answers,
            document_ids: doc ? [doc] : [],
            allocation,
          }),
        "Réponse transmise à la revue de l’agent.",
      );
    } catch {
      /* Notice shown by App */
    } finally {
      setPending(false);
    }
  };
  return (
    <form className="response-form" onSubmit={submit}>
      {request.questions.map((q, i) => (
        <label key={q.question_id}>
          {q.text_fr}
          {q.scope_note_fr && <small>{q.scope_note_fr}</small>}
          {q.answer_kind === "CHOICE" && q.choices?.length ? (
            <select
              required={i === 0}
              value={answers[q.question_id] || ""}
              onChange={(e) =>
                setAnswers({ ...answers, [q.question_id]: e.target.value })
              }
            >
              <option value="">Choisir…</option>
              {q.choices.map((choice) => (
                <option key={choice} value={choice}>
                  {choiceLabel[choice] || choice}
                </option>
              ))}
            </select>
          ) : q.answer_kind === "NUMBER" || q.answer_kind === "DATE" ? (
            <input
              type={q.answer_kind === "DATE" ? "date" : "number"}
              step={q.answer_kind === "NUMBER" ? "any" : undefined}
              min={q.answer_kind === "NUMBER" ? "0" : undefined}
              value={answers[q.question_id] || ""}
              onChange={(e) =>
                setAnswers({ ...answers, [q.question_id]: e.target.value })
              }
            />
          ) : (
            <textarea
              rows={3}
              required={i === 0 && q.answer_kind !== "DOCUMENT"}
              value={answers[q.question_id] || ""}
              onChange={(e) =>
                setAnswers({ ...answers, [q.question_id]: e.target.value })
              }
            />
          )}
        </label>
      ))}
      <label>
        Pièce justificative existante
        <select value={doc} onChange={(e) => setDoc(e.target.value)}>
          <option value="">Aucune pièce jointe</option>
          {c.documents.map((d) => (
            <option key={d.document.document_id} value={d.document.document_id}>
              {d.document.original_filename}
            </option>
          ))}
        </select>
      </label>
      <div className="attachment-row">
        <div className="file-field">
          <span>Ou joindre un nouveau PDF, 10 Mo maximum</span>
          <input
            ref={attachmentInput}
            className="visually-hidden"
            type="file"
            accept="application/pdf,.pdf"
            aria-label="Nouveau PDF pour la réponse"
            onChange={(e) => setAttachment(e.target.files?.[0] || null)}
          />
          <div className="file-choice">
            <button
              type="button"
              className="secondary"
              onClick={() => attachmentInput.current?.click()}
            >
              Choisir un PDF
            </button>
            <span>
              {attachment?.name || "Aucune nouvelle pièce sélectionnée"}
            </span>
          </div>
        </div>
        <button
          type="button"
          className="secondary"
          disabled={!attachment || uploadPending || pending}
          onClick={uploadAttachment}
        >
          {uploadPending ? "Dépôt en cours…" : "Déposer cette pièce"}
        </button>
        {uploadError && (
          <p className="error-text" role="alert">
            {uploadError}
          </p>
        )}
      </div>
      <div className="allocation-input">
        <strong>Proposition de répartition (facultatif)</strong>
        <p>La proposition reste en attente de validation humaine.</p>
        <label>
          Opération et ligne concernées
          <select
            value={targetIndex}
            onChange={(e) => setTargetIndex(Number(e.target.value))}
          >
            {targets.map((target, index) => (
              <option
                key={`${target.transaction_id}:${target.line_id}`}
                value={index}
              >
                {c.transactions.find(
                  (transaction) =>
                    transaction.transaction_id === target.transaction_id,
                )?.invoice_number || target.transaction_id}{" "}
                · {target.line_id}
              </option>
            ))}
          </select>
        </label>
        <div className="allocation-projects">
          <div className="allocation-project">
            <label>
              Premier projet
              <select
                value={projectOne}
                onChange={(e) => setProjectOne(e.target.value)}
              >
                {c.projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Quantité du premier projet
              <input
                type="number"
                min="0"
                step="any"
                value={quantityOne}
                onChange={(e) => setQuantityOne(e.target.value)}
              />
            </label>
          </div>
          <div className="allocation-project">
            <label>
              Second projet
              <select
                value={projectTwo}
                onChange={(e) => setProjectTwo(e.target.value)}
              >
                {c.projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Quantité du second projet
              <input
                type="number"
                min="0"
                step="any"
                value={quantityTwo}
                onChange={(e) => setQuantityTwo(e.target.value)}
              />
            </label>
          </div>
        </div>
        {allocationError && (
          <p className="error-text" role="alert">
            {allocationError}
          </p>
        )}
      </div>
      <button className="primary" disabled={pending || uploadPending}>
        {pending ? "Envoi…" : "Transmettre la réponse"}
      </button>
    </form>
  );
}

function Officer({
  caseView: c,
  tab,
  act,
  setTab,
  onSelectCase,
}: {
  caseView: OfficerCaseView;
  tab: Tab;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
  setTab: (tab: Tab) => void;
  onSelectCase: (caseId: string) => void;
}) {
  if (tab === "queue") return <Queue onSelectCase={onSelectCase} />;
  if (tab === "company360") return <Company360Tab c={c} />;
  if (tab === "network") return <NetworkOverview c={c} />;
  if (tab === "notifications") return <ActionNotifications c={c} />;
  if (tab === "advanced")
    return (
      <>
        <SectionHead
          label="PARAMÈTRES"
          title="Avancé"
          detail="Références, journal et diagnostics du dossier."
        />
        <details>
          <summary>Références</summary>
          <References c={c} />
        </details>
        <details>
          <summary>Timeline du dossier</summary>
          <HistoryPanel c={c} />
        </details>
        <details>
          <summary>Journal d’audit</summary>
          <AuditPanel caseId={c.case_id} caseVersion={c.case_version} />
        </details>
        <details>
          <summary>Diagnostics</summary>
          <Diagnostics c={c} />
        </details>
      </>
    );
  return (
    <>
      <SectionHead
        label="REVUE DOCUMENTAIRE"
        title={c.case_id}
        detail={`${c.company_display_name} · Version ${c.case_version} · Calcul déterministe`}
      />
      <nav className="dossier-jump" aria-label="Sections du dossier">
        <a href="#dossier-synthese">Synthèse</a>
        <a href="#dossier-causes">Pourquoi ?</a>
        <a href="#dossier-preuves">Preuves</a>
        <a href="#dossier-actions">Actions</a>
        <a href="#dossier-timeline">Timeline</a>
        <a href="#dossier-decision">Décision</a>
      </nav>
      <div className="dossier-hero" id="dossier-synthese">
        <div className="priority-ring">
          <div>
            <span>Priorité de revue</span>
            <strong>{format(c.score?.review_index)}</strong>
            <small>Indice documentaire</small>
          </div>
        </div>
        <div className="hero-copy">
          <span className="eyebrow">DOSSIER EN COURS</span>
          <h2>Une lecture claire des écarts et des pièces</h2>
          <p>
            Les contrôles déterministes structurent la revue. L’agent décide de
            l’usage des nouveaux éléments.
          </p>
          <div className="tags">
            {badge(c.mode_by_node.checks || "NOT_RUN")}
            <span className="badge">Validation humaine</span>
          </div>
        </div>
        <div className="hero-metrics">
          <div>
            <span>Couverture des preuves</span>
            <strong>
              {format(c.score?.evidence_coverage)}
              {c.score?.evidence_coverage ? " %" : ""}
            </strong>
            <small>
              {c.score?.coverage_complete
                ? "Complète"
                : "Partielle ou inconnue"}
            </small>
          </div>
          <div>
            <span>Clarification</span>
            <strong className="text-value">
              {status[c.score?.clarification_status || ""] ||
                c.score?.clarification_status ||
                "N/D"}
            </strong>
          </div>
          <div className="triage-metric">
            <span>Urgence de traitement (triage)</span>
            <strong>{format(c.triage?.triage_priority)}</strong>
            <small>Distincte de l’indice de revue</small>
          </div>
          <div>
            <span>Signal historique</span>
            <strong className="text-value">
              {indicator(c.history_signal_index, c.history_signal_status)}
            </strong>
          </div>
          <div>
            <span>Confiance opérationnelle</span>
            <strong className="text-value">
              {indicator(
                c.operational_confidence_index,
                c.operational_confidence_status,
              )}
            </strong>
          </div>
        </div>
      </div>
      {c.triage && c.triage.reason_codes.length > 0 && (
        <div className="tags triage-reasons" aria-label="Raisons du triage">
          {c.triage.reason_codes.map((code) => (
            <span className="badge" key={code}>
              {triageLabel[code] || code}
            </span>
          ))}
        </div>
      )}
      <p className="hero-caption">
        <CircleHelp size={15} /> Indice de priorisation documentaire calculé par
        les contrôles déterministes.
      </p>
      {c.operational_confidence_sample_note_fr && (
        <p className="hero-caption">
          {c.operational_confidence_sample_note_fr}
        </p>
      )}
      {c.indicators && (
        <details className="panel">
          <summary>Comprendre les cinq indicateurs</summary>
          {Object.entries(c.indicators).map(([code, value]) => (
            <article className="indicator-factor" key={code}>
              <strong>
                {(
                  {
                    document_review: "Indice de revue",
                    evidence_coverage: "Couverture des preuves",
                    historical_signal: "Signal historique",
                    urgency: "Urgence",
                    operational_confidence: "Confiance opérationnelle",
                  } as Record<string, string>
                )[code] ?? code}{" "}
                : {value.value ?? "Données insuffisantes"}
              </strong>
              <p>{value.explanation}</p>
              <small>
                Échantillon : {value.sample_size} · Calcul :{" "}
                {date(value.calculated_at)} · Règle : {value.rule_version}
              </small>
              {value.factors.map((factor) => (
                <p key={factor.code}>
                  {factor.explanation}
                  {factor.contribution !== null
                    ? ` · Contribution : ${factor.contribution}`
                    : ""}
                </p>
              ))}
            </article>
          ))}
        </details>
      )}
      <section id="dossier-causes" className="dossier-zone">
        <h2>Pourquoi ce dossier ?</h2>
        <Panel title="Contributions au score" eyebrow="EXPLICATION PAR CAUSE">
          {c.score?.cause_progress.length ? (
            <div className="cause-list">
              {c.score.cause_progress.map((cause) => (
                <article
                  className="cause-row"
                  key={`${cause.transaction_id}:${cause.family}`}
                >
                  <div>
                    <strong>{familyLabel[cause.family] || cause.family}</strong>
                    <small>{cause.transaction_id}</small>
                    <small>{cause.reason_code || "Cause documentée"}</small>
                    <span>{progressLabel[cause.stage] || cause.stage}</span>
                    {cause.provisional && (
                      <>
                        <em>Réduction provisoire</em>
                        <small>Validation agent requise</small>
                      </>
                    )}
                    <small>
                      Cause initiale : +
                      {cause.initial_weight ?? cause.raw_contribution} ·
                      Contribution actuelle : +{cause.current_contribution}
                    </small>
                    {cause.resolved_by && (
                      <small>
                        Résolue par {cause.resolved_by} · {cause.resolved_at}
                      </small>
                    )}
                    {cause.rule_version && (
                      <small>Règle : {cause.rule_version}</small>
                    )}
                  </div>
                  <strong className="cause-value">
                    {cause.raw_contribution} → {cause.current_contribution}
                  </strong>
                </article>
              ))}
            </div>
          ) : (
            <p>Aucune contribution chiffrée pour ce dossier.</p>
          )}
        </Panel>
        <Panel
          eyebrow="SIMULATION · AUCUN EFFET SUR LE DOSSIER"
          title="Impact si résolu"
        >
          <p>Score actuel : {format(c.score?.review_index)}</p>
          {c.impact_if_resolved?.length ? (
            <ol className="impact-list">
              {c.impact_if_resolved.map((step) => (
                <li key={step.cause_id}>
                  <strong>
                    Si {familyLabel[step.family] || step.family} ·{" "}
                    {step.transaction_id} est confirmée comme résolue
                  </strong>
                  <span>
                    {step.before_index} → {step.after_index}
                  </span>
                  <small>
                    Sources :{" "}
                    {step.source_ids.join(", ") || "Constat du dossier"} · règle{" "}
                    {step.rule_version}
                  </small>
                </li>
              ))}
            </ol>
          ) : (
            <p>Simulation indisponible pour les causes de cette version.</p>
          )}
          <p className="footnote">
            Simulation — aucune modification appliquée au dossier. Les étapes
            supposent une validation successivement confirmée par l’agent.
          </p>
        </Panel>
      </section>
      <section id="dossier-preuves" className="dossier-zone">
        <h2>Preuves</h2>
        <div className="dossier-counts">
          <span>
            <strong>{c.documents.length}</strong> pièces disponibles
          </span>
          <span>
            <strong>
              {
                c.documents.filter(
                  (document) =>
                    document.processing_status === "ANALYZED_AWAITING_REVIEW",
                ).length
              }
            </strong>{" "}
            à vérifier
          </span>
          <span>
            <strong>
              {
                new Set(
                  c.recommended_actions?.flatMap(
                    (action) => action.required_documents,
                  ) ?? [],
                ).size
              }
            </strong>{" "}
            types de pièces demandés
          </span>
        </div>
        <details className="dossier-secondary">
          <summary>Examiner les pièces et leurs analyses</summary>
          <Documents c={c} />
        </details>
      </section>
      <section id="dossier-actions" className="dossier-zone">
        <h2>Actions</h2>
        <p>
          {
            c.requests.filter(
              (item) => item.request.status === "PUBLISHED_IN_DEMO",
            ).length
          }{" "}
          demandes en attente ·{" "}
          {
            c.proposals.filter(
              (item) => item.status === "AWAITING_HUMAN_REVIEW",
            ).length
          }{" "}
          propositions à décider
        </p>
        <Panel
          title="Actions recommandées"
          eyebrow="PROCHAINE ÉTAPE · DÉCISION AGENT"
        >
          {c.recommended_actions?.length ? (
            c.recommended_actions.map((action) => (
              <article key={action.action_id} className="document">
                <strong>
                  Priorité {action.priority} · {action.title_fr}
                </strong>
                <span>
                  {action.status === "COMPLETED"
                    ? "Terminé"
                    : action.status === "WAITING"
                      ? "En attente"
                      : "À traiter"}
                </span>
                <p>{action.reason}</p>
                <small>
                  Causes :{" "}
                  {action.source_causes.join(", ") || "Aucune cause liée"}
                </small>
                {action.required_documents.length > 0 && (
                  <small>
                    Pièces requises : {action.required_documents.join(", ")}
                  </small>
                )}
              </article>
            ))
          ) : (
            <p>Aucune action recommandée avec les données actuelles.</p>
          )}
        </Panel>
      </section>
      <section id="dossier-timeline" className="dossier-zone">
        <h2>Timeline</h2>
        <HistoryPanel c={c} />
      </section>
      <section id="dossier-decision" className="dossier-zone">
        <h2>Décision de l’agent</h2>
        <div className="two-col">
          <Clarification c={c} act={act} />
          <Proposals c={c} act={act} />
          <CaseReviewPanel c={c} act={act} />
        </div>
        <p className="footnote">
          Accepter ou rejeter une proposition exige une pièce liée. La décision
          crée une nouvelle version du dossier.
        </p>
      </section>
      <InvestigationAssistant caseId={c.case_id} caseVersion={c.case_version} />
      <details className="dossier-secondary">
        <summary>Analyses complémentaires</summary>
        <div className="two-col indicator-explanations">
          <Panel
            title="Facteurs historiques"
            eyebrow="CONTEXTE · SÉPARÉ DU SCORE"
          >
            {c.history_signal_status === "AVAILABLE" ? (
              <>
                <p>
                  Indice historique : {format(c.history_signal_index)}/100 ·{" "}
                  {c.history_signal_method}
                </p>
                {c.history_signal_factors.length ? (
                  <div className="indicator-factor-list">
                    {c.history_signal_factors.map((factor) => (
                      <article
                        className="indicator-factor"
                        key={factor.reason_code}
                      >
                        <strong>
                          {factor.reason_code} · +{factor.contribution}
                        </strong>
                        <span>{factor.explanation_fr}</span>
                        <small>{factor.source_signal_ids.join(", ")}</small>
                      </article>
                    ))}
                  </div>
                ) : (
                  <p>
                    Aucune variation significative sur les périodes couvertes.
                  </p>
                )}
              </>
            ) : (
              <p>
                Données insuffisantes pour comparer l’entreprise à son
                historique.
              </p>
            )}
          </Panel>
          <Panel
            title="Facteurs de confiance"
            eyebrow="INTERACTIONS · SÉPARÉE DU SCORE"
          >
            {c.operational_confidence_status === "AVAILABLE" ? (
              <>
                <p>
                  Indice : {format(c.operational_confidence_index)}/100 ·{" "}
                  {c.operational_confidence_eligible_observations} observations
                  admissibles
                </p>
                <p>
                  Calcul au {c.operational_confidence_as_of} ·{" "}
                  {c.operational_confidence_method}
                </p>
                <div className="indicator-factor-list">
                  {c.operational_confidence_factors.map((factor, index) => (
                    <article
                      className="indicator-factor"
                      key={`${factor.code}:${index}`}
                    >
                      <strong>
                        {factor.code} · {factor.weighted_contribution} points
                      </strong>
                      <span>
                        {factor.numerator}/{factor.denominator}{" "}
                        {confidenceUnit[factor.code] ||
                          "observations favorables"}
                      </span>
                      <span>
                        Poids : {factor.effective_weight} % (nominal{" "}
                        {factor.nominal_weight} %)
                      </span>
                      <span>{factor.explanation_fr}</span>
                      <small>{factor.reason_codes.join(", ")}</small>
                      <small>{factor.source_ids.join(", ")}</small>
                    </article>
                  ))}
                </div>
              </>
            ) : (
              <p>
                Données insuffisantes :{" "}
                {c.operational_confidence_eligible_observations}/3 observations
                admissibles.
              </p>
            )}
          </Panel>
        </div>
        {c.behavior_profile && (
          <Panel
            title="Habitude et période observée"
            eyebrow="BASELINE PROPRE À L’ENTREPRISE"
          >
            <p>
              Période : {c.behavior_profile.observed_period} · Données arrêtées
              au {c.behavior_profile.as_of} · Règle{" "}
              {c.behavior_profile.rule_version}
            </p>
            <div className="monthly-context">
              {c.behavior_profile.metrics.map((metric) => (
                <article key={`${metric.code}-${metric.currency ?? "all"}`}>
                  <strong>{metric.label_fr}</strong>
                  <span>
                    Observé : {metric.current_value ?? "inconnu"} {metric.unit}{" "}
                    {metric.currency}
                  </span>
                  <span>
                    Habitude :{" "}
                    {metric.baseline_value ?? "données insuffisantes"}{" "}
                    {metric.unit}
                  </span>
                  {metric.change_percent !== null && (
                    <span>Écart : {metric.change_percent} %</span>
                  )}
                  <small>
                    {metric.sample_size} mois de référence exploitables
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
          </Panel>
        )}
        <Panel
          title="Comportement sur 12 mois"
          eyebrow="FENÊTRE CALENDAIRE · COUVERTURE EXPLICITE"
        >
          {c.monthly_activity.length ? (
            <div className="monthly-context">
              {c.monthly_activity.slice(-12).map((month) => (
                <article key={month.month}>
                  <strong>{month.month}</strong>
                  <span>
                    {month.transaction_count} transactions ·{" "}
                    {month.invoice_observation_count} observations de factures
                  </span>
                  <small>{month.source_label}</small>
                  <small>
                    {month.coverage_status === "COVERED"
                      ? "Période couverte"
                      : "Couverture inconnue"}
                  </small>
                </article>
              ))}
            </div>
          ) : (
            <p>Données insuffisantes pour la vue sur 12 mois.</p>
          )}
        </Panel>
      </details>
      <details className="dossier-secondary">
        <summary>Enquête détaillée et simulations</summary>
        <InvestigatorPanel
          brief={c.investigator_brief}
          passages={c.candidate_passages}
        />
        <div className="two-col">
          <QuantityStory c={c} />
        </div>
        <div className="two-col">
          <Findings findings={c.findings} />
        </div>
        <div className="two-col">
          <InvoiceCompare
            observations={c.invoice_observations}
            comparisons={c.invoice_comparisons}
          />
          <HypothesisCards
            hypotheses={c.investigator_brief?.top_hypotheses ?? []}
          />
        </div>
        <ContextAssessment ctx={c.context_assessment} />
        <ScenarioCards
          reviewIndex={c.score?.review_index}
          scenarios={c.scenarios}
        />
      </details>
    </>
  );
}

function Queue({ onSelectCase }: { onSelectCase: (caseId: string) => void }) {
  const q = useInfiniteQuery({
    queryKey: ["queue"],
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => api.queue(pageParam),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
  });
  return (
    <>
      {q.isLoading ? (
        <Skeleton />
      ) : q.isError ? (
        <p role="alert">File indisponible : {q.error.message}</p>
      ) : (
        <>
          <Portfolio
            items={q.data?.pages.flatMap((page) => page.items) ?? []}
            onOpen={onSelectCase}
          />
          {q.hasNextPage && (
            <button
              className="secondary"
              disabled={q.isFetchingNextPage}
              onClick={() => q.fetchNextPage()}
            >
              {q.isFetchingNextPage
                ? "Chargement…"
                : "Charger plus de dossiers"}
            </button>
          )}
        </>
      )}
    </>
  );
}

function Company360Tab({ c }: { c: OfficerCaseView }) {
  const history = useQuery({
    queryKey: ["history", "OFFICER", c.case_id],
    queryFn: () => api.history("OFFICER", c.case_id),
  });
  return <Company360 c={c} history={history.data ?? null} />;
}

function QuantityStory({ c }: { c: OfficerCaseView }) {
  const line = c.invoice_observations.find(
    (o) => o.perspective === "BUYER_RECEIVED",
  )?.lines[0];
  const ref = c.quantity_references[0];
  const gap = c.findings.find((f) => f.family === "QUANTITY");
  const allocations = c.allocations.filter(
    (allocation) =>
      allocation.status === "ACCEPTED" && allocation.line_id === line?.line_id,
  );
  return (
    <Panel eyebrow="RAPPROCHEMENT" title="Quantités documentées">
      <div className="quantity-compare">
        <div>
          <span>Achat observé</span>
          <strong>{format(line?.quantity)}</strong>
          <small>{line?.unit || ""}</small>
        </div>
        <ArrowRight size={23} />
        <div>
          <span>Référence {ref?.project_id || ""}</span>
          <strong>{format(ref?.quantity)}</strong>
          <small>{ref?.unit || ""}</small>
        </div>
      </div>
      <div className="gap-line">
        <span>Écart constaté par les contrôles</span>
        <strong>
          {format(gap?.quantity_difference)} {gap?.unit || ""}
        </strong>
      </div>
      {allocations.length > 0 && (
        <div className="allocation-summary">
          <span>Répartition enregistrée dans ce dossier</span>
          <div>
            {allocations.map((allocation) => (
              <span className="badge" key={allocation.allocation_id}>
                {allocation.target_project_id || "Autre"} ·{" "}
                {allocation.quantity} {allocation.unit}
              </span>
            ))}
          </div>
        </div>
      )}
      <p className="footnote">
        Les valeurs et le constat proviennent du dossier et des contrôles du
        service.
      </p>
    </Panel>
  );
}
function Findings({ findings }: { findings: Finding[] }) {
  return (
    <Panel eyebrow="CONTRÔLES" title="Constats">
      <div className="stack">
        {findings.map((f) => (
          <article className="finding" key={f.finding_id}>
            <div className="record-top">
              <strong>{familyLabel[f.family] || f.family}</strong>
              {badge(f.status)}
            </div>
            <div className="finding-value">
              {f.quantity_difference
                ? `${f.quantity_difference} ${f.unit || ""}`
                : status[f.status] || f.status}
            </div>
            <p>
              Motif : {format(f.reason_code)} · Calcul : {f.calculation_version}
            </p>
            <small>
              Références :{" "}
              {f.evidence_refs
                .map((r) => r.document_id || r.source_record_id)
                .filter(Boolean)
                .join(", ") || "N/D"}
            </small>
          </article>
        ))}
      </div>
    </Panel>
  );
}
function Observations({ c }: { c: OfficerCaseView }) {
  return (
    <Panel eyebrow="PERSPECTIVES" title="Observations de facture">
      <div className="observation-grid">
        {c.invoice_observations.map((o, i) => (
          <article className="observation" key={i}>
            <span className="eyebrow">
              {status[o.perspective] || o.perspective}
            </span>
            <strong className="mono">{o.invoice_number}</strong>
            <dl>
              <div>
                <dt>Émetteur</dt>
                <dd>{format(o.issuer_company_id)}</dd>
              </div>
              <div>
                <dt>Acheteur</dt>
                <dd>{format(o.buyer_company_id)}</dd>
              </div>
              <div>
                <dt>Date</dt>
                <dd>{date(o.issued_on)}</dd>
              </div>
              <div>
                <dt>Montant brut</dt>
                <dd>{money(o.gross_millimes)}</dd>
              </div>
              <div>
                <dt>Document</dt>
                <dd className="mono">{o.document_id}</dd>
              </div>
              <div>
                <dt>Origine</dt>
                <dd>{o.origin_group_id}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
      <p className="footnote">
        Les différences affichées sont descriptives. Les constats officiels sont
        ceux des contrôles.
      </p>
    </Panel>
  );
}

function Clarification({
  c,
  act,
}: {
  c: OfficerCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [draft, setDraft] = useState<ClarificationDraft | null>(null);
  const [pending, setPending] = useState(false);
  const run = async (job: () => Promise<unknown>, success: string) => {
    if (pending) return;
    setPending(true);
    try {
      return await act(job, success);
    } catch {
      return null;
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel eyebrow="CLARIFICATION" title="Demande de précision">
      {draft ? (
        <>
          <p>{draft.text_fr}</p>
          <ul className="question-list">
            {draft.questions.map((q) => (
              <li key={q.question_id}>{q.text_fr}</li>
            ))}
          </ul>
          <button
            className="primary"
            disabled={pending}
            onClick={async () => {
              const value = await run(
                () => api.publish(c.case_id, draft.draft_id, c.case_version),
                "Demande publiée dans la boîte de démonstration.",
              );
              if (value) setDraft(null);
            }}
          >
            {pending ? "Publication…" : "Publier dans la boîte de démo"}
          </button>
        </>
      ) : (
        <>
          <p className="muted">
            Les demandes neutres sont publiées automatiquement après chaque
            dépôt de l’entreprise. Une demande supplémentaire reste possible.
          </p>
          <button
            className="secondary"
            disabled={pending}
            onClick={async () => {
              const value = await run(
                () => api.prepare(c.case_id, c.case_version),
                "Brouillon prêt à relire.",
              );
              if (value) setDraft(value as ClarificationDraft);
            }}
          >
            Préparer la demande <ArrowRight size={16} />
          </button>
        </>
      )}
      {c.requests.length ? (
        <div className="request-mini">
          <strong>Demandes existantes</strong>
          {c.requests.map((r) => (
            <div className="list-row" key={r.request.request_id}>
              <span>
                <span className="mono">{r.request.request_id}</span>
                {r.request.origin === "AUTOMATIC" && (
                  <span className="auto-badge small">
                    Demande automatique BOUSSLA
                  </span>
                )}
                {r.request.target_response_at && (
                  <small>
                    Cible de réponse de démonstration :{" "}
                    {date(r.request.target_response_at)}
                  </small>
                )}
                {r.request.overdue_state === "FOLLOW_UP_DUE" && (
                  <small className="follow-up">Relance à prévoir</small>
                )}
              </span>
              {badge(r.request.status)}
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  );
}
function CaseReviewPanel({
  c,
  act,
}: {
  c: OfficerCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const canClose =
    c.score?.review_index === 0 &&
    !c.proposals.some(
      (proposal) => proposal.status === "AWAITING_HUMAN_REVIEW",
    ) &&
    !c.requests.some(
      (request) =>
        request.request.status === "PUBLISHED_IN_DEMO" ||
        request.request.status === "EXTENDED",
    );
  const send = async (kind: "ACCEPT" | "REJECT" | "ESCALATE" | "RESOLVE") => {
    if (pending || reason.trim().length < 10) return;
    setPending(true);
    try {
      await act(
        () => api.caseDecision(c.case_id, c.case_version, kind, reason.trim()),
        "Décision de revue interne enregistrée.",
      );
      setReason("");
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel eyebrow="DÉCISION DU DOSSIER" title="Décision de revue interne">
      <p>
        Motif obligatoire. Cette décision ne modifie pas l’indice documentaire
        et n’a aucun effet juridique automatique.
      </p>
      <label htmlFor="case-review-reason">Motif de la décision</label>
      <textarea
        id="case-review-reason"
        value={reason}
        maxLength={500}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className="button-row">
        <button
          className="secondary"
          disabled={pending || reason.trim().length < 10}
          onClick={() => send("ESCALATE")}
        >
          Escalader le dossier
        </button>
        <button
          className="secondary"
          disabled={pending || reason.trim().length < 10}
          onClick={() => send("REJECT")}
        >
          Rejeter la revue
        </button>
        <button
          className="secondary"
          disabled={pending || reason.trim().length < 10 || !canClose}
          onClick={() => send("ACCEPT")}
        >
          Accepter la revue
        </button>
        <button
          className="primary"
          disabled={pending || reason.trim().length < 10 || !canClose}
          onClick={() => send("RESOLVE")}
        >
          Résoudre le dossier
        </button>
      </div>
      {!canClose && (
        <p className="footnote">
          Pour accepter ou résoudre, toutes les causes et propositions doivent
          être closes et aucune demande ne doit attendre une réponse.
        </p>
      )}
      {!!c.case_decisions?.length && (
        <ol className="timeline">
          {[...c.case_decisions].reverse().map((decision) => (
            <li key={decision.decision_id}>
              <span className="timeline-version">v{decision.case_version}</span>
              <div>
                <strong>{decision.kind}</strong>
                <p>{decision.reason}</p>
                <small>
                  {decision.actor_id} · {decision.decided_at} · indice{" "}
                  {decision.review_index ?? "inconnu"}
                </small>
              </div>
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}

function Proposals({
  c,
  act,
}: {
  c: OfficerCaseView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const [pending, setPending] = useState(false);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const run = async (p: EvidenceProposal, action: "accept" | "reject") => {
    const reason = (reasons[p.proposal_id] || "").trim();
    if (pending || reason.length < 10) return;
    setPending(true);
    try {
      await act(
        () =>
          api.decide(c.case_id, p.proposal_id, c.case_version, action, reason),
        action === "accept"
          ? "Pièce acceptée dans ce dossier."
          : "Proposition rejetée.",
      );
      setReasons((current) => ({ ...current, [p.proposal_id]: "" }));
    } catch {
      /* Notice shown by App */
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel eyebrow="VALIDATION HUMAINE" title="Propositions d’affectation">
      {c.proposals.length ? (
        c.proposals.map((p) => (
          <article className="proposal" key={p.proposal_id}>
            <div className="record-top">
              <span className="mono">{p.proposal_id}</span>
              {badge(p.status)}
            </div>
            <p>
              Transaction {p.transaction_id} · ligne {p.line_id}
            </p>
            <p>Pièce source : {format(p.source_document_id)}</p>
            <div className="changes">
              {p.changes.map((ch) => (
                <div key={ch.allocation_id}>
                  <strong>{ch.target_project_id || "Autre"}</strong>
                  <span>
                    {format(ch.old_quantity)} → {ch.new_quantity} {p.unit}
                  </span>
                </div>
              ))}
            </div>
            {p.status === "AWAITING_HUMAN_REVIEW" && (
              <>
                <label htmlFor={`reason-${p.proposal_id}`}>
                  Motif de la décision sur la pièce
                </label>
                <textarea
                  id={`reason-${p.proposal_id}`}
                  value={reasons[p.proposal_id] || ""}
                  maxLength={500}
                  onChange={(event) =>
                    setReasons((current) => ({
                      ...current,
                      [p.proposal_id]: event.target.value,
                    }))
                  }
                />
                <div className="button-row">
                  <button
                    className="primary"
                    disabled={
                      pending ||
                      !p.source_document_id ||
                      (reasons[p.proposal_id] || "").trim().length < 10
                    }
                    onClick={() => run(p, "accept")}
                  >
                    Accepter dans ce dossier
                  </button>
                  <button
                    className="secondary"
                    disabled={
                      pending ||
                      (reasons[p.proposal_id] || "").trim().length < 10
                    }
                    onClick={() => run(p, "reject")}
                  >
                    Rejeter
                  </button>
                </div>
              </>
            )}
            {!p.source_document_id && p.status === "AWAITING_HUMAN_REVIEW" && (
              <p className="footnote">
                Une déclaration seule ne suffit pas à accepter cette
                répartition.
              </p>
            )}
          </article>
        ))
      ) : (
        <Empty>Aucune proposition en attente.</Empty>
      )}
    </Panel>
  );
}

function References({ c }: { c: OfficerCaseView }) {
  return (
    <>
      <SectionHead
        label="AIDE À LA REVUE"
        title="Passages de référence candidats à examiner"
        detail="Ces sources sont candidates ; l’agent vérifie leur applicabilité."
      />
      {c.reference_note && (
        <Panel
          eyebrow={`AI ASSISTÉ · ${c.reference_note.generation_mode}`}
          title="Synthèse assistée à partir des passages retrouvés"
        >
          <p className="note-summary">{c.reference_note.summary_fr}</p>
          <div className="tags">
            {c.reference_note.candidate_rule_ids.map((id) => (
              <a className="badge" href={`#rule-${id}`} key={id}>
                {id}
              </a>
            ))}
          </div>
          {c.reference_note.applicability_questions.map((q, i) => (
            <p key={i} className="question">
              {q}
            </p>
          ))}
          <p className="footnote">
            Synthèse indicative — l’applicabilité doit être vérifiée par
            l’agent.
          </p>
        </Panel>
      )}
      <div className="reference-grid">
        {c.candidate_passages.length ? (
          c.candidate_passages.map((p) => (
            <article
              className="reference panel"
              id={`rule-${p.rule_id}`}
              key={p.rule_id}
            >
              <div className="record-top">
                <span className="badge">Référence candidate</span>
                {badge(p.mode)}
              </div>
              <h2>{p.document_title}</h2>
              <p className="mono">
                {p.rule_id} {p.article ? `· ${p.article}` : ""}{" "}
                {p.page ? `· p. ${p.page}` : ""}
              </p>
              <blockquote>{p.text}</blockquote>
              {p.source_url.startsWith("https://") && (
                <a
                  href={p.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Consulter la source <ArrowRight size={15} />
                </a>
              )}
            </article>
          ))
        ) : (
          <Panel
            eyebrow="RECHERCHE DE RÉFÉRENCES"
            title="Aucun passage candidat retourné"
          >
            <p className="muted">
              Le service n’a renvoyé aucun passage pour les constats de cette
              version. Une synthèse ne peut être affichée sans sources citées.
            </p>
            <div className="tags">
              {badge(c.mode_by_node.retrieval || "NOT_RUN")}
              {badge(c.mode_by_node.reference_note || "NOT_RUN")}
            </div>
          </Panel>
        )}
      </div>
    </>
  );
}

function InvestigationAssistant({
  caseId,
  caseVersion,
}: {
  caseId: string;
  caseVersion: number;
}) {
  const [question, setQuestion] = useState(
    "Pourquoi ce dossier est prioritaire ?",
  );
  const [answer, setAnswer] = useState<InvestigationAnswer | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const scope = `${caseId}:${caseVersion}`;
  const currentScope = useRef(scope);
  currentScope.current = scope;
  useEffect(() => {
    setAnswer(null);
    setError("");
  }, [scope]);
  const ask = async (event: FormEvent) => {
    event.preventDefault();
    if (pending || question.trim().length < 3) return;
    setPending(true);
    setError("");
    setAnswer(null);
    const requestedScope = scope;
    try {
      const result = await api.askInvestigation(caseId, question.trim());
      if (currentScope.current === requestedScope) setAnswer(result);
    } catch (cause) {
      if (currentScope.current === requestedScope)
        setError(
          cause instanceof Error ? cause.message : "Réponse indisponible.",
        );
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel
      eyebrow="ASSISTANCE SOURCÉE · AGENT"
      title="Assistant d’investigation"
    >
      <form onSubmit={ask} className="investigation-form">
        <label>
          Question sur ce dossier
          <input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            maxLength={500}
          />
        </label>
        <button
          className="primary"
          disabled={pending || question.trim().length < 3}
        >
          {pending ? "Recherche…" : "Examiner les sources"}
        </button>
      </form>
      <p className="footnote">
        Questions possibles : priorité, historique, documents, réseau,
        références ou décisions. La réponse n’est pas une décision automatique.
      </p>
      {error && <p role="alert">{error}</p>}
      {answer && (
        <div className="investigation-answer">
          <p className="investigation-lines">{answer.answer_fr}</p>
          <strong>Sources citées</strong>
          {answer.citations.length ? (
            <ul>
              {answer.citations.map((citation) => (
                <li key={citation.source_id}>
                  {citation.source_url?.startsWith("https://") ? (
                    <a
                      href={citation.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {citation.label_fr}
                    </a>
                  ) : (
                    citation.label_fr
                  )}
                  <small>
                    {" "}
                    · {citation.kind} · {citation.source_id}
                  </small>
                </li>
              ))}
            </ul>
          ) : (
            <p>Aucune source suffisante pour une conclusion.</p>
          )}
          <small>
            v{answer.case_version} · {answer.rule_version} · {answer.mode} ·{" "}
            {answer.limitations.join(" ")}
          </small>
        </div>
      )}
    </Panel>
  );
}

function AuditPanel({
  caseId,
  caseVersion,
}: {
  caseId: string;
  caseVersion: number;
}) {
  const audit = useQuery({
    queryKey: ["audit", caseId, caseVersion],
    queryFn: () => api.audit(caseId),
  });
  if (audit.isLoading) return <p>Chargement du journal d’audit…</p>;
  if (audit.isError) return <p role="alert">Journal d’audit indisponible.</p>;
  const records = audit.data?.records ?? [];
  return (
    <Panel eyebrow="DÉCISIONS ET CALCULS ENREGISTRÉS" title="Journal d’audit">
      <p className="footnote">
        Journal local de traçabilité ; ce n’est pas une preuve légale
        infalsifiable.
      </p>
      {!!audit.data?.legacy_events_without_audit && (
        <p className="footnote">
          {audit.data.legacy_events_without_audit} ancien(s) événement(s) sans
          détail d’audit.
        </p>
      )}
      {records.length ? (
        <ol className="timeline">
          {[...records].reverse().map((record) => (
            <li key={record.audit_id}>
              <span className="timeline-version">v{record.case_version}</span>
              <div>
                <strong>{record.action}</strong>
                <p>{record.reason}</p>
                <small>
                  {record.actor_id} ·{" "}
                  {new Date(record.at).toLocaleString("fr-FR")}
                </small>
                {(record.before || record.after) && (
                  <p className="timeline-score">
                    Indice de revue : {record.before?.review_index ?? "inconnu"}{" "}
                    → {record.after?.review_index ?? "inconnu"}
                  </p>
                )}
                {Object.keys({
                  ...record.before?.cause_contributions,
                  ...record.after?.cause_contributions,
                })
                  .filter(
                    (causeId) =>
                      record.before?.cause_contributions?.[causeId] !==
                      record.after?.cause_contributions?.[causeId],
                  )
                  .map((causeId) => (
                    <p className="timeline-cause" key={causeId}>
                      Cause {causeId} :{" "}
                      {record.before?.cause_contributions?.[causeId] ??
                        "inconnue"}{" "}
                      →{" "}
                      {record.after?.cause_contributions?.[causeId] ??
                        "inconnue"}
                    </p>
                  ))}
                {!!record.evidence_ids.length && (
                  <p>Sources : {record.evidence_ids.join(", ")}</p>
                )}
                {!!record.fact_changes?.length && (
                  <details className="audit-facts">
                    <summary>
                      Valeurs modifiées ({record.fact_changes.length})
                    </summary>
                    {record.fact_changes.map((change) => (
                      <div key={`${change.kind}:${change.fact_id}`}>
                        <strong>
                          {change.kind} · {change.fact_id}
                        </strong>
                        <pre>
                          Avant :{" "}
                          {JSON.stringify(change.before ?? "absent", null, 2)}
                        </pre>
                        <pre>
                          Après :{" "}
                          {JSON.stringify(change.after ?? "retiré", null, 2)}
                        </pre>
                      </div>
                    ))}
                  </details>
                )}
                <small>
                  Règle : {record.rules_version ?? "inconnue"} · Moteur :{" "}
                  {record.engine_version ?? "inconnu"} · {record.event_id}
                </small>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p>Aucune entrée d’audit enregistrée pour ce dossier.</p>
      )}
    </Panel>
  );
}

function HistoryPanel({ c }: { c: OfficerCaseView }) {
  const q = useQuery({
    queryKey: ["history", "OFFICER", c.case_id],
    queryFn: () => api.history("OFFICER", c.case_id),
  });
  return (
    <>
      <SectionHead
        label="TRAÇABILITÉ"
        title="Historique du dossier"
        detail="Chaque révision conserve la version précédente."
      />
      {q.isLoading ? (
        <Skeleton />
      ) : q.isError ? (
        <p role="alert">Historique indisponible.</p>
      ) : (
        <>
          <Timeline value={q.data!} />
          {q.data?.operational_confidence_changes?.length ? (
            <Panel
              eyebrow="CONFIANCE OPÉRATIONNELLE · AGENT"
              title="Évolution expliquée"
            >
              <div className="indicator-factor-list">
                {q.data.operational_confidence_changes.map((change, index) => (
                  <article
                    className="indicator-factor"
                    key={`${change.to_version}:${change.as_of}:${index}`}
                  >
                    <strong>
                      Confiance :{" "}
                      {change.before_index === null
                        ? "données insuffisantes"
                        : format(change.before_index)}{" "}
                      →{" "}
                      {change.after_index === null
                        ? "données insuffisantes"
                        : format(change.after_index)}
                    </strong>
                    <small>
                      Version {change.from_version} → {change.to_version} ·{" "}
                      {change.as_of}
                    </small>
                    {change.factor_deltas.map((factor) => (
                      <div key={factor.code}>
                        <span>
                          {factor.code} :{" "}
                          {factor.before_contribution ?? "inconnu"} →{" "}
                          {factor.after_contribution ?? "inconnu"} points
                        </span>
                        <small>{factor.source_ids.join(", ")}</small>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
            </Panel>
          ) : null}
        </>
      )}
    </>
  );
}
function Timeline({ value }: { value: HistoryView }) {
  const revisions = [...(value.revisions ?? [])].reverse();
  const byVersion = new Map(
    (value.revisions ?? []).map((revision) => [revision.version, revision]),
  );
  return (
    <Panel eyebrow="RÉVISIONS IMMUABLES" title="Chronologie">
      <ol className="timeline">
        {revisions.map((revision) => {
          const previous =
            revision.parent_version === null
              ? null
              : byVersion.get(revision.parent_version);
          const before = previous?.score_snapshot;
          const after = revision.score_snapshot;
          const changedCauses =
            before && after
              ? after.cause_progress.flatMap((cause) => {
                  const prior = before.cause_progress.find(
                    (item) =>
                      item.cause_id === cause.cause_id ||
                      (item.transaction_id === cause.transaction_id &&
                        item.family === cause.family),
                  );
                  return prior &&
                    prior.current_contribution !== cause.current_contribution
                    ? [{ cause, prior }]
                    : [];
                })
              : [];
          const events = (value.events ?? [])
            .filter((event) => event.case_version === revision.version)
            .sort((left, right) => left.at.localeCompare(right.at));
          return (
            <li key={revision.version}>
              <span className="timeline-version">v{revision.version}</span>
              <div>
                <strong>{revision.reason}</strong>
                <p>
                  {new Date(revision.created_at).toLocaleString("fr-FR", {
                    dateStyle: "short",
                    timeStyle: "short",
                  })}
                </p>
                {before &&
                  after &&
                  before.review_index !== after.review_index && (
                    <p className="timeline-score">
                      Indice de revue : {format(before.review_index)} →{" "}
                      {format(after.review_index)}
                    </p>
                  )}
                {changedCauses.map(({ cause, prior }) => (
                  <p
                    className="timeline-cause"
                    key={`${cause.transaction_id}:${cause.family}`}
                  >
                    {familyLabel[cause.family] || cause.family} ·{" "}
                    {cause.transaction_id} : {prior.current_contribution} →{" "}
                    {cause.current_contribution}
                    {cause.provisional
                      ? " · provisoire"
                      : cause.resolved_by
                        ? " · validée par l’agent"
                        : ""}
                    {cause.evidence_ids?.length
                      ? ` · preuves ${cause.evidence_ids?.join(", ")}`
                      : ""}
                  </p>
                ))}
                {events.map((event) => (
                  <div className="timeline-event" key={event.event_id}>
                    <time dateTime={event.at}>
                      {new Date(event.at).toLocaleTimeString("fr-FR", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                    <span>{event.summary}</span>
                    {event.actor_id && <small> · {event.actor_id}</small>}
                    {!!event.fact_ids?.length && (
                      <small> · {event.fact_ids.join(", ")}</small>
                    )}
                  </div>
                ))}
                <small>
                  Version précédente :{" "}
                  {revision.parent_version === null
                    ? "origine"
                    : `v${revision.parent_version}`}
                </small>
              </div>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}

function Diagnostics({ c }: { c: OfficerCaseView }) {
  const modes = c.mode_by_node;
  return (
    <>
      <SectionHead
        label="TRANSPARENCE"
        title="Diagnostics du système"
        detail="Les modes affichés viennent du service pour cette version du dossier."
      />
      <Panel eyebrow="ÉTAT DES COMPOSANTS" title="Chaîne de traitement">
        <div className="diag-grid">
          {Object.entries(modes).map(([name, mode]) => (
            <div className="diag-row" key={name}>
              <span>{nodeLabel[name] || name}</span>
              {badge(mode)}
            </div>
          ))}
        </div>
        <div className="legend">
          {(["LIVE", "TEMPLATE", "MANUAL", "NOT_RUN", "ERROR"] as Mode[]).map(
            (mode) => (
              <div key={mode}>
                {badge(mode)}
                <span>
                  {mode === "LIVE"
                    ? "Service exécuté"
                    : mode === "TEMPLATE"
                      ? "Repli déterministe"
                      : mode === "MANUAL"
                        ? "Traitement manuel"
                        : mode === "NOT_RUN"
                          ? "Non exécuté"
                          : "Échec signalé"}
                </span>
              </div>
            ),
          )}
        </div>
      </Panel>
    </>
  );
}

export default function App() {
  if (
    window.location.pathname !== "/" &&
    window.location.pathname !== "/index.html"
  ) {
    return (
      <main className="fatal">
        <span className="eyebrow">PAGE INTROUVABLE</span>
        <h1>Cette page n’existe pas.</h1>
        <p>Le dossier reste accessible depuis l’accueil BOUSSLA.</p>
        <a className="primary" href="/">
          Retour au dossier
        </a>
      </main>
    );
  }
  return (
    <ErrorBoundary>
      <AppInner />
    </ErrorBoundary>
  );
}

function TranscriptionForm({
  c,
  document,
  act,
}: {
  c: CompanyCaseView;
  document: DocumentView;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
}) {
  const proposal = document.extraction!;
  const [fields, setFields] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      (proposal.candidates ?? []).map((field) => [
        field.field_name,
        field.normalized_value ?? field.raw_value ?? "",
      ]),
    ),
  );
  const [pending, setPending] = useState(false);
  const labels: Record<string, string> = {
    "allocation.transaction_id": "Transaction",
    "allocation.line_id": "Ligne de facture",
    "allocation.company_id": "Entreprise",
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    try {
      await act(
        () =>
          api.confirmTranscription(
            c.case_id,
            proposal.proposal_id!,
            c.case_version,
            fields,
          ),
        "Champs vérifiés. Analyse mise à jour ; validation de l’agent requise.",
      );
    } catch {
      /* App displays the typed error. */
    } finally {
      setPending(false);
    }
  };
  return (
    <Panel
      title="Vérifier les champs du document"
      eyebrow={document.document.original_filename}
    >
      <p>
        Comparez les valeurs avec votre pièce. Cette confirmation porte sur la
        transcription ; la décision appartient à l’agent.
      </p>
      <form className="context-form transcription-form" onSubmit={submit}>
        {Object.entries(fields).map(([name, value]) => (
          <label key={name}>
            {labels[name] ??
              (name.startsWith("allocation.")
                ? `Quantité · ${name.split(".")[1]}`
                : name)}
            <input
              value={value}
              onChange={(event) =>
                setFields({ ...fields, [name]: event.target.value })
              }
            />
          </label>
        ))}
        <button className="primary" disabled={pending}>
          {pending ? "Vérification…" : "Confirmer les champs"}
        </button>
      </form>
    </Panel>
  );
}
