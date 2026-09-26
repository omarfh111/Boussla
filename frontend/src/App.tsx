import {
  Component,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardList,
  Compass,
  FileText,
  FolderOpen,
  History,
  LayoutDashboard,
  RefreshCw,
  Search,
  UploadCloud,
} from "lucide-react";
import { ApiError, api } from "./api/client";
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
} from "./api/types";

type Tab =
  | "overview"
  | "operations"
  | "context"
  | "requests"
  | "documents"
  | "queue"
  | "dossier"
  | "references"
  | "history"
  | "diagnostics";
const companyTabs: [Tab, string, ReactNode][] = [
  ["overview", "Vue d’ensemble", <LayoutDashboard size={18} />],
  ["operations", "Opérations", <Activity size={18} />],
  ["context", "Contexte", <ClipboardList size={18} />],
  ["requests", "Demandes", <FolderOpen size={18} />],
  ["documents", "Pièces", <FileText size={18} />],
];
const officerTabs: [Tab, string, ReactNode][] = [
  ["queue", "File de revue", <LayoutDashboard size={18} />],
  ["dossier", "Dossier", <Search size={18} />],
  ["references", "Références", <BookOpen size={18} />],
  ["history", "Historique", <History size={18} />],
  ["diagnostics", "Diagnostics", <Activity size={18} />],
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
  OTHER_OR_UNKNOWN: "Autre / inconnu",
};
const familyLabel: Record<string, string> = {
  COUNTERPARTY: "Concordance des observations",
  SETTLEMENT: "Règlement observé",
  QUANTITY: "Affectation des quantités",
};
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
  const [role, setRole] = useState<Role>("OFFICER");
  const [tab, setTab] = useState<Tab>("queue");
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState<RevisionResult | null>(null);
  const locked = useRef(false);
  const bootstrap = useQuery({
    queryKey: ["bootstrap", role],
    queryFn: () => api.bootstrap(role),
  });
  const caseId = bootstrap.data?.case_ids[0];
  const caseQuery = useQuery({
    queryKey: ["case", role, caseId],
    queryFn: () => api.case(role, caseId!),
    enabled: !!caseId,
  });
  const current = caseQuery.data;
  const switchRole = (next: Role) => {
    if (next === role) return;
    setRole(next);
    setTab(next === "COMPANY" ? "overview" : "queue");
    setNotice("");
    setRevision(null);
    query.removeQueries({ queryKey: ["case"] });
    query.removeQueries({ queryKey: ["history"] });
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
  const tabs = role === "COMPANY" ? companyTabs : officerTabs;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Compass size={22} />
          </span>
          <span>
            BOUSSLA<small>Espace de revue</small>
          </span>
        </div>
        <div className="workspace-label">
          ESPACE {role === "COMPANY" ? "ENTREPRISE" : "AGENT"}
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
          {bootstrap.isLoading || caseQuery.isLoading ? (
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
            <Company caseView={current} tab={tab} act={act} />
          ) : (
            <Officer caseView={current} tab={tab} act={act} setTab={setTab} />
          )}
        </main>
      </div>
      {revision && (
        <Revision value={revision} close={() => setRevision(null)} />
      )}
    </div>
  );
}

function Company({
  caseView: c,
  tab,
  act,
}: {
  caseView: CompanyCaseView;
  tab: Tab;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
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
        <div className="two-col">
          <Operations c={c} compact />
          <Panel eyebrow="VOTRE SITUATION" title="Actions à poursuivre">
            <div className="next-step">
              <span className="step-num">01</span>
              <div>
                <strong>Renseigner le contexte</strong>
                <p>Usage prévu, projet et bénéficiaire.</p>
              </div>
            </div>
            <div className="next-step">
              <span className="step-num">02</span>
              <div>
                <strong>Vérifier les demandes</strong>
                <p>
                  Une réponse reste une déclaration jusqu’à la revue humaine.
                </p>
              </div>
            </div>
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
  if (tab === "context")
    return (
      <>
        <SectionHead
          label="DÉCLARATION"
          title="Contexte de l’opération"
          detail="Contexte déclaré par l’entreprise — il ne constitue pas à lui seul une preuve."
        />
        <ContextForm c={c} act={act} />
      </>
    );
  if (tab === "requests")
    return (
      <>
        <SectionHead
          label="ÉCHANGES"
          title="Demandes de précision"
          detail="Les questions publiées par l’agent apparaissent ici."
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
    try {
      await act(
        () =>
          api.context(
            c.case_id,
            c.case_version,
            Object.fromEntries([...data].filter(([, value]) => value !== "")),
          ),
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
              <option value="LONG_LIVED_ASSET">Actif durable</option>
              <option value="OTHER_OR_UNKNOWN">Autre / à préciser</option>
            </select>
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
          <button className="primary wide" disabled={pending}>
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
                  {claim.beneficiary_type} · {format(claim.stage)}
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
                  <div>
                    <dt>SHA-256</dt>
                    <dd className="mono">{short(d.document.sha256)}</dd>
                  </div>
                  <div>
                    <dt>Extraction</dt>
                    <dd>{d.extraction?.status || "N/D"}</dd>
                  </div>
                </dl>
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
          <Panel
            key={r.request.request_id}
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
            <p>{r.text_fr}</p>
            <ul className="question-list">
              {r.questions.map((q) => (
                <li key={q.question_id}>{q.text_fr}</li>
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
            <p className="footnote">Déclaration seule ≠ preuve acceptée.</p>
          </Panel>
        ))
      ) : (
        <Empty>Aucune demande publiée pour ce dossier.</Empty>
      )}
    </div>
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
          <textarea
            rows={3}
            required={i === 0}
            value={answers[q.question_id] || ""}
            onChange={(e) =>
              setAnswers({ ...answers, [q.question_id]: e.target.value })
            }
          />
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
}: {
  caseView: OfficerCaseView;
  tab: Tab;
  act: (job: () => Promise<unknown>, success: string) => Promise<unknown>;
  setTab: (tab: Tab) => void;
}) {
  if (tab === "queue") return <Queue setTab={setTab} />;
  if (tab === "references") return <References c={c} />;
  if (tab === "history") return <HistoryPanel c={c} />;
  if (tab === "diagnostics") return <Diagnostics c={c} />;
  return (
    <>
      <SectionHead
        label="REVUE DOCUMENTAIRE"
        title={c.case_id}
        detail={`${c.company_display_name} · Version ${c.case_version} · Calcul déterministe`}
      />
      <div className="dossier-hero">
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
        </div>
      </div>
      <p className="hero-caption">
        <CircleHelp size={15} /> Indice de priorisation documentaire calculé par
        les contrôles déterministes — pas une probabilité de fraude.
      </p>
      <div className="two-col">
        <QuantityStory c={c} />
        <Clarification c={c} act={act} />
      </div>
      <div className="two-col">
        <Findings findings={c.findings} />
        <Proposals c={c} act={act} />
      </div>
      <div className="two-col">
        <Observations c={c} />
        <Panel eyebrow="HYPOTHÈSES" title="Pistes examinées">
          {c.hypotheses.length ? (
            c.hypotheses.map((h) => (
              <div className="list-row" key={h.hypothesis_id}>
                <div>
                  <strong>{h.hypothesis_id}</strong>
                  <small>{h.scope}</small>
                </div>
                {badge(h.status)}
              </div>
            ))
          ) : (
            <Empty>Aucune hypothèse disponible.</Empty>
          )}
        </Panel>
      </div>
      <Panel eyebrow="SIMULATION HYPOTHÉTIQUE" title="Scénarios de sensibilité">
        <p className="footnote">
          Ces scénarios n’altèrent pas l’état canonique du dossier.
        </p>
        {c.scenarios.map((s) => (
          <div className="list-row" key={s.scenario_id}>
            <strong>{s.label}</strong>
            <span className="mono">
              {Object.entries(s.outputs)
                .map(
                  ([key, value]) =>
                    `${scenarioLabel[key] || key}: ${status[String(value)] || String(value)}`,
                )
                .join(" · ")}
            </span>
          </div>
        ))}
      </Panel>
    </>
  );
}

function Queue({ setTab }: { setTab: (tab: Tab) => void }) {
  const q = useQuery({ queryKey: ["queue"], queryFn: api.queue });
  return (
    <>
      <SectionHead
        label="PRIORISATION"
        title="File de revue"
        detail="Les dossiers sont ordonnés selon les contrôles déterministes disponibles."
      />
      <Panel
        eyebrow="DOSSIERS ASSIGNÉS"
        title="À examiner"
        action={
          <span className="badge">{q.data?.items.length ?? "—"} dossiers</span>
        }
      >
        {q.isLoading ? (
          <Skeleton />
        ) : q.isError ? (
          <p role="alert">File indisponible : {q.error.message}</p>
        ) : !q.data?.items.length ? (
          <Empty>Aucun dossier assigné.</Empty>
        ) : (
          <div className="queue-list">
            {q.data.items.map((item) => (
              <button
                className="queue-item"
                key={item.case_id}
                onClick={() => setTab("dossier")}
              >
                <div className="queue-company">
                  <span className="queue-icon">
                    <FolderOpen size={21} />
                  </span>
                  <div>
                    <strong>{item.company_display_name}</strong>
                    <small>
                      {item.case_id} · v{item.case_version}
                    </small>
                  </div>
                </div>
                <div>
                  <small>Priorité de revue</small>
                  <strong className="priority-number">
                    {format(item.review_index)}
                  </strong>
                </div>
                <div>
                  <small>Couverture des preuves</small>
                  <strong>
                    {format(item.evidence_coverage)}
                    {item.evidence_coverage ? " %" : ""}
                  </strong>
                </div>
                <div>
                  <small>Constats actifs</small>
                  <strong>{item.active_finding_count}</strong>
                </div>
                <div>{badge(item.clarification_status)}</div>
                <ChevronRight size={19} />
              </button>
            ))}
          </div>
        )}
      </Panel>
      <p className="footnote">
        <CircleHelp size={14} /> Indice de priorisation documentaire calculé par
        les contrôles déterministes — pas une probabilité de fraude.
      </p>
    </>
  );
}

function QuantityStory({ c }: { c: OfficerCaseView }) {
  const line = c.invoice_observations.find(
    (o) => o.perspective === "BUYER_RECEIVED",
  )?.lines[0];
  const ref = c.quantity_references[0];
  const gap = c.findings.find((f) => f.family === "QUANTITY");
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
              {o.perspective.replaceAll("_", " ")}
            </span>
            <strong className="mono">{o.invoice_number}</strong>
            <dl>
              <div>
                <dt>Montant brut</dt>
                <dd>{money(o.gross_millimes)}</dd>
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
    <Panel eyebrow="ACTION HUMAINE" title="Demande de précision">
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
            Préparer une demande neutre à partir des constats actuels.
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
              <span className="mono">{r.request.request_id}</span>
              {badge(r.request.status)}
            </div>
          ))}
        </div>
      ) : null}
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
  const run = async (p: EvidenceProposal, action: "accept" | "reject") => {
    if (pending) return;
    setPending(true);
    try {
      await act(
        () => api.decide(c.case_id, p.proposal_id, c.case_version, action),
        action === "accept"
          ? "Pièce acceptée dans ce dossier."
          : "Proposition rejetée.",
      );
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
              <div className="button-row">
                <button
                  className="primary"
                  disabled={pending || !p.source_document_id}
                  onClick={() => run(p, "accept")}
                >
                  Accepter dans ce dossier
                </button>
                <button
                  className="secondary"
                  disabled={pending}
                  onClick={() => run(p, "reject")}
                >
                  Rejeter
                </button>
              </div>
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
        <Timeline value={q.data!} />
      )}
    </>
  );
}
function Timeline({ value }: { value: HistoryView }) {
  return (
    <Panel eyebrow="RÉVISIONS IMMUABLES" title="Chronologie">
      <ol className="timeline">
        {[...value.revisions].reverse().map((r) => (
          <li key={r.version}>
            <span className="timeline-version">v{r.version}</span>
            <div>
              <strong>{r.reason}</strong>
              <p>
                {date(r.created_at)} ·{" "}
                {value.events
                  .filter((e) => e.case_version === r.version)
                  .map((e) => e.summary)
                  .join(" · ")}
              </p>
              <small>
                Version précédente :{" "}
                {r.parent_version === null ? "origine" : `v${r.parent_version}`}
              </small>
            </div>
          </li>
        ))}
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
              <span>{name}</span>
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
