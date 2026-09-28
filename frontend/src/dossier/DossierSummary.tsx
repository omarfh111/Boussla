import type { OfficerCaseView } from "../api/types";
import { triageLabel } from "../portfolio/components";

const value = (item: string | number | null | undefined) =>
  item === null || item === undefined || item === ""
    ? "Non communiqué"
    : String(item);

export function DossierSummary({ c }: { c: OfficerCaseView }) {
  const awaitingReview = c.documents.filter(
    (document) => document.processing_status === "ANALYZED_AWAITING_REVIEW",
  ).length;
  const pendingProposals = c.proposals.filter(
    (proposal) => proposal.status === "AWAITING_HUMAN_REVIEW",
  ).length;
  const pendingRequests = c.requests.filter(
    (request) => request.request.status === "PUBLISHED_IN_DEMO",
  ).length;
  const coverage = c.score?.evidence_coverage;
  const coverageWidth =
    coverage === null || coverage === undefined
      ? 0
      : Math.min(100, Math.max(0, Number(coverage) || 0));
  const clarification: Record<string, string> = {
    NOT_REQUESTED: "Aucune demande",
    PUBLISHED_IN_DEMO: "En attente de réponse",
    RESPONDED: "Réponse reçue",
    PENDING: "En attente",
    FOLLOW_UP_DUE: "Relance à prévoir",
  };

  return (
    <section
      className="dossier-overview"
      id="dossier-synthese"
      aria-labelledby="dossier-title"
    >
      <header className="dossier-heading">
        <span className="eyebrow">
          REVUE DOCUMENTAIRE · DONNÉES SYNTHÉTIQUES
        </span>
        <h1 id="dossier-title">{c.company_display_name}</h1>
        <p>
          {c.case_id} <span aria-hidden="true">·</span> Version {c.case_version}
        </p>
      </header>
      <nav className="dossier-jump" aria-label="Sections du dossier">
        <a href="#dossier-synthese">Synthèse</a>
        <a href="#dossier-causes">Pourquoi ?</a>
        <a href="#dossier-preuves">Preuves</a>
        <a href="#dossier-actions">Actions</a>
        <a href="#dossier-timeline">Timeline</a>
        <a href="#dossier-decision">Décision</a>
      </nav>
      <div className="dossier-command">
        <div className="dossier-priority">
          <span className="eyebrow">PRIORITÉ DOCUMENTAIRE</span>
          <span>Priorité de revue</span>
          <strong>{value(c.score?.review_index)}</strong>
          <small>Contributions déterministes du dossier</small>
        </div>
        <div className="dossier-command-body">
          <div className="dossier-command-top">
            <div>
              <span className="eyebrow">ÉTAT DU DOSSIER</span>
              <h2>Ce qui attend votre revue</h2>
            </div>
            <a href="#dossier-decision">
              Voir les décisions <span aria-hidden="true">→</span>
            </a>
          </div>
          <div className="dossier-status-grid">
            <div className="dossier-status dossier-coverage">
              <span>Couverture des preuves</span>
              <strong>
                {coverage === null || coverage === undefined
                  ? "Non communiqué"
                  : `${coverage} %`}
              </strong>
              <span className="dossier-coverage-track" aria-hidden="true">
                <span style={{ width: `${coverageWidth}%` }} />
              </span>
              <small>
                {c.score?.coverage_complete
                  ? "Complète"
                  : "Partielle ou inconnue"}
              </small>
            </div>
            <div className="dossier-status">
              <span>Urgence de traitement</span>
              <strong>{value(c.triage?.triage_priority)}</strong>
              <small>Ordre opérationnel · distinct de la revue</small>
            </div>
            <div className="dossier-status dossier-clarification">
              <span>Clarification</span>
              <strong>
                {clarification[c.score?.clarification_status ?? ""] ||
                  value(c.score?.clarification_status)}
              </strong>
              <small>
                {pendingRequests} demande{pendingRequests > 1 ? "s" : ""} en
                attente
              </small>
            </div>
          </div>
          <div className="dossier-pending">
            <a href="#dossier-preuves">
              <strong>{awaitingReview}</strong> pièce
              {awaitingReview > 1 ? "s" : ""} à vérifier
            </a>
            <a href="#dossier-decision">
              <strong>{pendingProposals}</strong> proposition
              {pendingProposals > 1 ? "s" : ""} à décider
            </a>
            <a href="#dossier-actions">
              Voir les actions recommandées <span aria-hidden="true">→</span>
            </a>
          </div>
        </div>
      </div>
      <details className="dossier-context">
        <summary>Contexte de triage et autres indicateurs</summary>
        <div className="dossier-context-grid">
          <div>
            <h3>Motifs d’urgence</h3>
            {c.triage?.reason_codes.length ? (
              <ul>
                {c.triage.reason_codes.map((code) => (
                  <li key={code}>{triageLabel[code] || code}</li>
                ))}
              </ul>
            ) : (
              <p>Aucun motif supplémentaire signalé.</p>
            )}
          </div>
          <div>
            <h3>Signal historique</h3>
            <p>
              {c.history_signal_status === "AVAILABLE"
                ? value(c.history_signal_index)
                : "Données insuffisantes"}
            </p>
            <h3>Confiance opérationnelle</h3>
            <p>
              {c.operational_confidence_status === "AVAILABLE"
                ? value(c.operational_confidence_index)
                : "Données insuffisantes"}
            </p>
          </div>
        </div>
        {c.operational_confidence_sample_note_fr && (
          <p>{c.operational_confidence_sample_note_fr}</p>
        )}
        <p>
          Le contexte historique et la confiance opérationnelle restent
          distincts de la priorité documentaire. Ces indicateurs décrivent des
          dimensions distinctes du travail de revue.
        </p>
      </details>
    </section>
  );
}
