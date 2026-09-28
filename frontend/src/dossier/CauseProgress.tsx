import type { CauseProgress } from "../api/types";

const stages: CauseProgress["stage"][] = [
  "UNRESOLVED",
  "EXPLANATION_RECEIVED",
  "EVIDENCE_RECEIVED",
  "EVIDENCE_COHERENT",
  "RESOLVED",
];
const stageLabels: Record<CauseProgress["stage"], string> = {
  UNRESOLVED: "Écart",
  EXPLANATION_RECEIVED: "Réponse",
  EVIDENCE_RECEIVED: "Pièce",
  EVIDENCE_COHERENT: "Cohérente",
  RESOLVED: "Résolue",
};
const stateLabels: Record<CauseProgress["stage"], string> = {
  UNRESOLVED: "Non expliquée",
  EXPLANATION_RECEIVED: "Réponse reçue",
  EVIDENCE_RECEIVED: "Pièce reçue, analyse en attente",
  EVIDENCE_COHERENT: "Pièce cohérente, validation en attente",
  RESOLVED: "Résolue après décision agent",
};
const familyLabels: Record<CauseProgress["family"], string> = {
  COUNTERPARTY: "Concordance des observations",
  SETTLEMENT: "Règlement observé",
  QUANTITY: "Affectation des quantités",
};

export function CauseProgressList({ causes }: { causes: CauseProgress[] }) {
  if (!causes.length)
    return <p>Aucune contribution chiffrée pour ce dossier.</p>;
  return (
    <div className="cause-progress-list">
      {causes.map((cause) => {
        const current = stages.indexOf(cause.stage);
        return (
          <article
            className={
              cause.provisional
                ? "cause-progress is-provisional"
                : "cause-progress"
            }
            key={cause.cause_id ?? `${cause.transaction_id}:${cause.family}`}
          >
            <div className="cause-progress-head">
              <div>
                <span className="eyebrow">{familyLabels[cause.family]}</span>
                <h3>{cause.transaction_id}</h3>
              </div>
              <div
                className="cause-progress-value"
                aria-label={`Contribution initiale ${cause.initial_weight ?? cause.raw_contribution}, contribution actuelle ${cause.current_contribution}`}
              >
                <span>+{cause.initial_weight ?? cause.raw_contribution}</span>
                <span aria-hidden="true">→</span>
                <strong>+{cause.current_contribution}</strong>
              </div>
            </div>
            <ol className="cause-steps" aria-label="Progression de la cause">
              {stages.map((stage, index) => (
                <li
                  key={stage}
                  className={
                    index < current
                      ? "is-done"
                      : index === current
                        ? "is-current"
                        : "is-next"
                  }
                  aria-current={index === current ? "step" : undefined}
                >
                  <span className="cause-step-mark" aria-hidden="true" />
                  <span>{stageLabels[stage]}</span>
                </li>
              ))}
            </ol>
            <div className="cause-progress-foot">
              <span className="cause-stage-label">
                {stateLabels[cause.stage]}
              </span>
              {cause.provisional && (
                <strong>Réduction provisoire · validation agent requise</strong>
              )}
              {cause.stage === "RESOLVED" && !cause.provisional && (
                <strong>Résolution confirmée</strong>
              )}
            </div>
            <details>
              <summary>Provenance et règle</summary>
              <p>
                Motif : {cause.reason_code || "Cause documentée"} · Règle :{" "}
                {cause.rule_version || "Non communiquée"}
              </p>
              <p>
                Sources : {cause.source_ids.join(", ") || "Non communiquées"}
              </p>
              {cause.resolved_by && (
                <p>
                  Résolue par {cause.resolved_by} · {cause.resolved_at}
                </p>
              )}
            </details>
          </article>
        );
      })}
    </div>
  );
}
