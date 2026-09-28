import { useMemo, useState } from "react";
import type { NetworkView, OfficerCaseView } from "../api/types";

type Node = NetworkView["nodes"][number];
type Edge = NetworkView["edges"][number];
type DisplayNode = Node & { x: number; y: number };
const kindLabel: Record<string, string> = {
  COMPANY: "Entreprise",
  CASE: "Dossier",
  TRANSACTION: "Transaction",
  PROJECT: "Projet",
  INVOICE: "Facture",
  PAYMENT: "Règlement",
  DOCUMENT: "Pièce",
  DELIVERY: "Livraison",
};
const groupLabel = ["Entreprises", "Opérations", "Pièces et règlements"];
const groupOf = (kind: string) =>
  kind === "COMPANY"
    ? 0
    : ["CASE", "TRANSACTION", "PROJECT"].includes(kind)
      ? 1
      : 2;
const nodeOrder = (a: Node, b: Node) =>
  groupOf(a.kind) - groupOf(b.kind) ||
  a.kind.localeCompare(b.kind) ||
  a.label.localeCompare(b.label, "fr") ||
  a.node_id.localeCompare(b.node_id);
const short = (text: string) =>
  text.length > 29 ? `${text.slice(0, 27)}…` : text;

/** Presentation-only filtering of service-provided graph entities and relations. */
export function filterEvidenceNetwork(
  graph: NetworkView,
  dossier: OfficerCaseView,
  search: string,
  fromMonth: string,
  toMonth: string,
  minimum: string,
  reviewOnly: boolean,
) {
  const reviewTransactions = new Set(
    dossier.findings
      .filter(
        (finding) => finding.status === "UNRESOLVED" && finding.transaction_id,
      )
      .map((finding) => `transaction:${finding.transaction_id}`),
  );
  const reviewNodes = new Set(reviewTransactions);
  for (const edge of graph.edges) {
    if (
      edge.case_id === dossier.case_id &&
      (reviewTransactions.has(edge.source) ||
        reviewTransactions.has(edge.target))
    ) {
      reviewNodes.add(edge.source);
      reviewNodes.add(edge.target);
    }
  }
  for (const edge of graph.edges) {
    if (
      edge.case_id === dossier.case_id &&
      edge.kind === "SELLS_TO" &&
      reviewNodes.has(edge.target)
    )
      reviewNodes.add(edge.source);
  }
  const term = search.trim().toLocaleLowerCase("fr");
  const companyMatches = new Set(
    graph.nodes
      .filter(
        (node) =>
          node.kind === "COMPANY" &&
          node.label.toLocaleLowerCase("fr").includes(term),
      )
      .map((node) => node.node_id),
  );
  const searchNodes = new Set(companyMatches);
  if (term)
    for (const edge of graph.edges) {
      if (companyMatches.has(edge.source) || companyMatches.has(edge.target)) {
        searchNodes.add(edge.source);
        searchNodes.add(edge.target);
      }
    }
  const threshold = Number(minimum) * 1000;
  const nodes = graph.nodes.filter((node) => {
    if (reviewOnly && !reviewNodes.has(node.node_id)) return false;
    if (term && !searchNodes.has(node.node_id)) return false;
    const month = (
      node.attributes.issued_on ||
      node.attributes.occurred_at ||
      node.attributes.economic_period ||
      ""
    ).slice(0, 7);
    if (
      month &&
      ((fromMonth && month < fromMonth) || (toMonth && month > toMonth))
    )
      return false;
    const amount =
      node.attributes.gross_millimes || node.attributes.amount_millimes;
    if (minimum && amount && Number(amount) < threshold) return false;
    return true;
  });
  const ids = new Set(nodes.map((node) => node.node_id));
  return {
    nodes,
    edges: graph.edges.filter(
      (edge) => ids.has(edge.source) && ids.has(edge.target),
    ),
  };
}

function layout(nodes: Node[]): { nodes: DisplayNode[]; height: number } {
  const groups: Node[][] = [[], [], []];
  for (const node of [...nodes].sort(nodeOrder))
    groups[groupOf(node.kind)].push(node);
  const height = Math.max(
    390,
    Math.max(...groups.map((group) => group.length)) * 58 + 92,
  );
  return {
    nodes: groups.flatMap((group, column) =>
      group.map((node, row) => ({
        ...node,
        x: [130, 460, 790][column],
        y: 76 + row * 58,
      })),
    ),
    height,
  };
}

export function EvidenceNetwork({
  graph,
  dossier,
}: {
  graph: NetworkView;
  dossier: OfficerCaseView;
}) {
  const [search, setSearch] = useState("");
  const [fromMonth, setFromMonth] = useState("");
  const [toMonth, setToMonth] = useState("");
  const [minimum, setMinimum] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [mode, setMode] = useState<"overview" | "all">("overview");
  const [selection, setSelection] = useState<{
    nodeId?: string;
    edgeId?: string;
  }>({});
  const filtered = useMemo(
    () =>
      filterEvidenceNetwork(
        graph,
        dossier,
        search,
        fromMonth,
        toMonth,
        minimum,
        reviewOnly,
      ),
    [graph, dossier, search, fromMonth, toMonth, minimum, reviewOnly],
  );
  const visible = useMemo(() => {
    const nodes =
      mode === "overview"
        ? filtered.nodes.filter((node) =>
            ["COMPANY", "CASE", "TRANSACTION"].includes(node.kind),
          )
        : filtered.nodes;
    const ids = new Set(nodes.map((node) => node.node_id));
    return {
      nodes,
      edges: filtered.edges.filter(
        (edge) => ids.has(edge.source) && ids.has(edge.target),
      ),
    };
  }, [filtered, mode]);
  const positions = useMemo(() => layout(visible.nodes), [visible.nodes]);
  const points = new Map(positions.nodes.map((node) => [node.node_id, node]));
  const sourceNodes = new Map(graph.nodes.map((node) => [node.node_id, node]));
  const selectedNode = visible.nodes.find(
    (node) => node.node_id === selection.nodeId,
  );
  const selectedEdge = visible.edges.find(
    (edge) => edge.edge_id === selection.edgeId,
  );
  const activeIds = new Set<string>();
  if (selectedNode) {
    activeIds.add(selectedNode.node_id);
    for (const edge of visible.edges)
      if (
        edge.source === selectedNode.node_id ||
        edge.target === selectedNode.node_id
      ) {
        activeIds.add(edge.source);
        activeIds.add(edge.target);
      }
  }
  if (selectedEdge) {
    activeIds.add(selectedEdge.source);
    activeIds.add(selectedEdge.target);
  }
  const focused = !!selectedNode || !!selectedEdge;
  const selectNode = (nodeId: string) => setSelection({ nodeId });
  const selectEdge = (edgeId: string) => setSelection({ edgeId });
  const selectedCompany =
    selectedNode?.kind === "COMPANY" ? selectedNode : null;
  const linkedInvoices = selectedCompany
    ? graph.edges.filter(
        (edge) =>
          (edge.kind === "ISSUED" || edge.kind === "RECEIVED") &&
          edge.source === selectedCompany.node_id,
      )
    : [];
  const invoiceTotals = new Map<string, number>();
  for (const edge of linkedInvoices) {
    const invoice = sourceNodes.get(edge.target);
    if (!invoice?.attributes.currency || !invoice.attributes.gross_millimes)
      continue;
    invoiceTotals.set(
      invoice.attributes.currency,
      (invoiceTotals.get(invoice.attributes.currency) ?? 0) +
        Number(invoice.attributes.gross_millimes),
    );
  }
  const relatedFindings =
    selectedEdge?.case_id === dossier.case_id
      ? dossier.findings.filter(
          (finding) =>
            finding.status === "UNRESOLVED" &&
            finding.transaction_id &&
            selectedEdge.source_ids.includes(finding.transaction_id),
        )
      : null;

  return (
    <section className="evidence-network" aria-label="Réseau de preuves">
      <div className="network-toolbar">
        <label className="network-search">
          Rechercher une entreprise
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nom de l’entreprise"
          />
        </label>
        <label>
          Vue
          <select
            value={mode}
            onChange={(event) => {
              setMode(event.target.value as "overview" | "all");
              setSelection({});
            }}
          >
            <option value="overview">Relations clés</option>
            <option value="all">Tous les éléments</option>
          </select>
        </label>
        <details className="network-more-filters">
          <summary>Filtres de faits</summary>
          <div>
            <label>
              Depuis
              <input
                type="month"
                value={fromMonth}
                onChange={(event) => setFromMonth(event.target.value)}
              />
            </label>
            <label>
              Jusqu’à
              <input
                type="month"
                value={toMonth}
                onChange={(event) => setToMonth(event.target.value)}
              />
            </label>
            <label>
              Montant minimum (TND)
              <input
                type="number"
                min="0"
                value={minimum}
                onChange={(event) => setMinimum(event.target.value)}
              />
            </label>
            <label className="network-check">
              <input
                type="checkbox"
                checked={reviewOnly}
                onChange={(event) => setReviewOnly(event.target.checked)}
              />{" "}
              Constats du dossier courant uniquement
            </label>
          </div>
        </details>
      </div>
      <p className="network-count" aria-live="polite">
        {visible.nodes.length} nœuds · {visible.edges.length} relations
        affichées
        {mode === "overview" && <span> · entreprises et opérations</span>}
      </p>
      <p className="network-scroll-hint">
        Faites défiler la carte horizontalement pour voir les autres colonnes.
      </p>
      <div className="network-workspace">
        <div className="network-map-wrap">
          {visible.nodes.length ? (
            <svg
              className="network-map"
              viewBox={`0 0 920 ${positions.height}`}
              role="group"
              aria-label="Carte des entités groupées par type et de leurs relations sourcées"
            >
              {groupLabel.map((label, index) => (
                <text
                  className="network-column-label"
                  x={[130, 460, 790][index]}
                  y="30"
                  textAnchor="middle"
                  key={label}
                >
                  {label}
                </text>
              ))}
              {visible.edges.map((edge) => {
                const a = points.get(edge.source),
                  b = points.get(edge.target);
                if (!a || !b) return null;
                const active =
                  selectedEdge?.edge_id === edge.edge_id ||
                  (!!selectedNode &&
                    (edge.source === selectedNode.node_id ||
                      edge.target === selectedNode.node_id));
                const middle = (a.x + b.x) / 2;
                return (
                  <path
                    key={edge.edge_id}
                    d={`M ${a.x} ${a.y} C ${middle} ${a.y}, ${middle} ${b.y}, ${b.x} ${b.y}`}
                    className={`network-link ${active ? "is-active" : ""} ${focused && !active ? "is-dim" : ""}`}
                    role="button"
                    tabIndex={0}
                    aria-label={`Relation ${sourceNodes.get(edge.source)?.label ?? edge.source} vers ${sourceNodes.get(edge.target)?.label ?? edge.target} · ${edge.kind}`}
                    onClick={() => selectEdge(edge.edge_id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        selectEdge(edge.edge_id);
                      }
                    }}
                  />
                );
              })}
              {positions.nodes.map((node) => (
                <g
                  key={node.node_id}
                  className={`network-node ${selectedNode?.node_id === node.node_id ? "is-selected" : ""} ${focused && !activeIds.has(node.node_id) ? "is-dim" : ""}`}
                  role="button"
                  tabIndex={0}
                  aria-label={`${kindLabel[node.kind] || node.kind} : ${node.label}`}
                  onClick={() => selectNode(node.node_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      selectNode(node.node_id);
                    }
                  }}
                >
                  <rect
                    x={node.x - 105}
                    y={node.y - 20}
                    width="210"
                    height="40"
                    rx="7"
                  />
                  <text
                    className="network-node-kind"
                    x={node.x - 96}
                    y={node.y - 5}
                  >
                    {kindLabel[node.kind] || node.kind}
                  </text>
                  <text
                    className="network-node-label"
                    x={node.x - 96}
                    y={node.y + 10}
                  >
                    {short(node.label)}
                  </text>
                  <title>{node.label}</title>
                </g>
              ))}
            </svg>
          ) : (
            <p className="network-empty">
              Aucun élément ne correspond aux filtres.
            </p>
          )}
        </div>
        <aside
          className="network-inspector"
          aria-label="Inspecteur du réseau"
          aria-live="polite"
        >
          <span className="eyebrow">INSPECTEUR</span>
          {selectedNode ? (
            <>
              <h2>{selectedNode.label}</h2>
              <p>
                {kindLabel[selectedNode.kind] || selectedNode.kind} ·{" "}
                {selectedNode.case_ids.length} dossier
                {selectedNode.case_ids.length > 1 ? "s" : ""}
              </p>
              <dl>
                <div>
                  <dt>Identifiant</dt>
                  <dd>{selectedNode.node_id}</dd>
                </div>
                <div>
                  <dt>Dossiers</dt>
                  <dd>
                    {selectedNode.case_ids.join(", ") || "Non communiqué"}
                  </dd>
                </div>
                {Object.entries(selectedNode.attributes).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              {selectedCompany && (
                <>
                  <p>{linkedInvoices.length} observations de facture liées</p>
                  <p>
                    {[...invoiceTotals]
                      .map(
                        ([currency, millimes]) =>
                          `${(millimes / 1000).toLocaleString("fr-TN")} ${currency}`,
                      )
                      .join(" · ") || "Montants indisponibles"}{" "}
                    (somme des observations, doublons de perspectives possibles)
                  </p>
                  <p>
                    Confiance opérationnelle :{" "}
                    {selectedCompany.node_id === `company:${dossier.company_id}`
                      ? (dossier.operational_confidence_index ??
                        "données insuffisantes")
                      : "non disponible pour cette entreprise"}
                  </p>
                </>
              )}
            </>
          ) : selectedEdge ? (
            <>
              <h2>
                {sourceNodes.get(selectedEdge.source)?.label ??
                  selectedEdge.source}{" "}
                →{" "}
                {sourceNodes.get(selectedEdge.target)?.label ??
                  selectedEdge.target}
              </h2>
              <p>
                {selectedEdge.kind} · dossier {selectedEdge.case_id}
              </p>
              <dl>
                <div>
                  <dt>Provenance</dt>
                  <dd>{selectedEdge.provenance_status}</dd>
                </div>
                <div>
                  <dt>Sources</dt>
                  <dd>
                    {selectedEdge.source_ids.join(", ") || "Non communiquées"}
                  </dd>
                </div>
                <div>
                  <dt>Constats du dossier courant</dt>
                  <dd>
                    {relatedFindings === null
                      ? "Écarts de cet autre dossier non chargés"
                      : `${relatedFindings.length} constat(s) actif(s)`}
                  </dd>
                </div>
              </dl>
              <p>Comparaison historique du lien non disponible.</p>
            </>
          ) : (
            <p>
              Sélectionnez une entité ou une relation pour inspecter ses faits
              et ses sources.
            </p>
          )}
        </aside>
      </div>
      <div className="network-alternatives">
        <details>
          <summary>Liste accessible des nœuds visibles</summary>
          <div className="network-entity-list">
            {visible.nodes.map((node) => (
              <button
                type="button"
                key={node.node_id}
                onClick={() => selectNode(node.node_id)}
              >
                <span>{kindLabel[node.kind] || node.kind}</span>
                {node.label}
              </button>
            ))}
          </div>
        </details>
        <details>
          <summary>Liste accessible des relations visibles</summary>
          <div className="network-entity-list">
            {visible.edges.map((edge) => (
              <button
                type="button"
                key={edge.edge_id}
                onClick={() => selectEdge(edge.edge_id)}
              >
                {sourceNodes.get(edge.source)?.label ?? edge.source} →{" "}
                {sourceNodes.get(edge.target)?.label ?? edge.target} ·{" "}
                {edge.kind}
              </button>
            ))}
          </div>
        </details>
      </div>
      <p className="footnote">
        Les colonnes indiquent le type d’entité ; la distance entre éléments ne
        mesure ni intensité ni gravité. Les filtres portent sur les faits datés
        et chiffrés du service.
      </p>
    </section>
  );
}
