import { Component, type ReactNode } from "react";
import { FolderOpen } from "lucide-react";
export class ErrorBoundary extends Component<
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

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <FolderOpen size={24} />
      <p>{children}</p>
    </div>
  );
}
export function Panel({
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
export function SectionHead({
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
export function Skeleton() {
  return (
    <div className="skeletons" role="status" aria-label="Chargement du dossier">
      <div />
      <div />
      <div />
    </div>
  );
}
export function Toast({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  return (
    <div className="toast" role="status">
      <span>{message}</span>
      <button type="button" aria-label="Fermer le message" onClick={onClose}>
        ×
      </button>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message?: string;
  onRetry: () => void;
}) {
  return (
    <div className="error-state" role="alert">
      <h1>Le dossier ne peut pas être chargé</h1>
      {message && <p>{message}</p>}
      <button className="primary" onClick={onRetry}>
        Réessayer
      </button>
    </div>
  );
}
