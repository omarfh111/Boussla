import type { ReactNode } from "react";
import {
  Building2,
  ChevronRight,
  ClipboardList,
  Database,
  FileText,
  FolderOpen,
  History,
  LayoutDashboard,
  RefreshCw,
  Search,
} from "lucide-react";
import { BousslaMark } from "../brand/BousslaMark";
import type { Role } from "../api/types";

export type Tab =
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

type NavItem = { id: Tab; label: string; icon: ReactNode };
const companyTabs: NavItem[] = [
  {
    id: "overview",
    label: "Mes dossiers",
    icon: <LayoutDashboard size={18} />,
  },
  { id: "requests", label: "Actions requises", icon: <FolderOpen size={18} /> },
  { id: "documents", label: "Documents", icon: <FileText size={18} /> },
  { id: "messages", label: "Messages", icon: <ClipboardList size={18} /> },
];
const officerTabs: NavItem[] = [
  {
    id: "queue",
    label: "Tableau de bord",
    icon: <LayoutDashboard size={18} />,
  },
  { id: "dossier", label: "Dossiers", icon: <Search size={18} /> },
  { id: "network", label: "Réseau", icon: <Building2 size={18} /> },
  { id: "company360", label: "Historique", icon: <History size={18} /> },
  {
    id: "notifications",
    label: "Notifications",
    icon: <ClipboardList size={18} />,
  },
  { id: "advanced", label: "Avancé", icon: <Database size={18} /> },
];
const operatorTabs: NavItem[] = [
  { id: "admin", label: "Données démo", icon: <Database size={18} /> },
];
const roleLabels: Record<Role, string> = {
  COMPANY: "Entreprise",
  OFFICER: "Agent",
  OPERATOR: "Opérateur démo",
};
const tabsFor = (role: Role) =>
  role === "COMPANY"
    ? companyTabs
    : role === "OPERATOR"
      ? operatorTabs
      : officerTabs;

type ShellProps = {
  role: Role;
  tab: Tab;
  onTabChange: (tab: Tab) => void;
  onRoleChange: (role: Role) => void;
  onRefresh: () => void | Promise<void>;
  caseId?: string;
  caseVersion?: number;
  modeBadge?: ReactNode;
  mode?: string;
  children: ReactNode;
};

export function AppShell({
  role,
  tab,
  onTabChange,
  onRoleChange,
  onRefresh,
  caseId,
  caseVersion,
  modeBadge,
  mode,
  children,
}: ShellProps) {
  const currentTab = tabsFor(role).find((item) => item.id === tab);
  return (
    <>
      <a className="skip-link" href="#main-content">
        Aller au contenu principal
      </a>
      <aside className="sidebar" aria-label="Espace et navigation">
        <div className="brand">
          <span className="brand-mark">
            <BousslaMark size={32} />
          </span>
          <span>
            BOUSSLA<small>Espace de revue</small>
          </span>
        </div>
        <div className="workspace-label">Espace {roleLabels[role]}</div>
        <nav aria-label="Navigation principale">
          {tabsFor(role).map(({ id, label, icon }) => (
            <button
              type="button"
              key={id}
              className={`nav-item ${tab === id ? "selected" : ""}`}
              aria-current={tab === id ? "page" : undefined}
              onClick={() => onTabChange(id)}
            >
              {icon}
              <span>{label}</span>
              {tab === id && (
                <ChevronRight
                  className="nav-chevron"
                  size={15}
                  aria-hidden="true"
                />
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="demo-pill">Données synthétiques</span>
          <p>
            Simulation locale de rôles — pas une authentification de production.
          </p>
          <div className="system">
            <span className="live-dot" aria-hidden="true" />
            Service local <span>{mode || "—"}</span>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs" aria-label="Emplacement actuel">
            <span>{roleLabels[role]}</span>
            <ChevronRight size={15} aria-hidden="true" />
            <strong>{currentTab?.label || "Dossier"}</strong>
            {caseId && <span className="case-ref">{caseId}</span>}
            {caseVersion !== undefined && (
              <span className="version">v{caseVersion}</span>
            )}
          </div>
          <div className="top-actions">
            {modeBadge}
            <div
              className="role-switch"
              role="group"
              aria-label="Rôle de démonstration"
            >
              {(["COMPANY", "OFFICER", "OPERATOR"] as const).map((item) => (
                <button
                  type="button"
                  key={item}
                  className={role === item ? "active" : ""}
                  aria-pressed={role === item}
                  onClick={() => onRoleChange(item)}
                  title={
                    item === "OPERATOR"
                      ? "Administration de données synthétiques — démonstration locale."
                      : undefined
                  }
                >
                  {roleLabels[item]}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="icon-button refresh-button"
              onClick={onRefresh}
              aria-label="Actualiser"
              title="Actualiser"
            >
              <RefreshCw size={17} />
            </button>
          </div>
        </header>
        <main id="main-content" className="content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </>
  );
}
