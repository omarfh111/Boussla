import { useEffect, useMemo, useRef, useState } from "react";
import type { NetworkView, OfficerCaseView } from "../api/types";

type Node = NetworkView["nodes"][number];
type Edge = NetworkView["edges"][number];
type Point = {
  id: string;
  x: number;
  y: number;
  radius: number;
  depth: number;
};
const colors: Record<string, string> = {
  COMPANY: "#52d3d7",
  INVOICE: "#f4ba60",
  PAYMENT: "#9bd77a",
  DOCUMENT: "#ae94ec",
  PROJECT: "#e58ca1",
  CASE: "#ffffff",
  TRANSACTION: "#6ba7ff",
  DELIVERY: "#d2c47c",
};

/** Deterministic 3D coordinates; no source data or meaning is encoded by position. */
function position(index: number, total: number) {
  const y = 1 - (2 * (index + 0.5)) / Math.max(total, 1);
  const radius = Math.sqrt(Math.max(0, 1 - y * y));
  const angle = index * Math.PI * (3 - Math.sqrt(5));
  return {
    x: Math.cos(angle) * radius * 190,
    y: y * 190,
    z: Math.sin(angle) * radius * 190,
  };
}
function project(
  point: { x: number; y: number; z: number },
  width: number,
  height: number,
  yaw: number,
  pitch: number,
  zoom: number,
) {
  const x = point.x * Math.cos(yaw) + point.z * Math.sin(yaw);
  const z = point.z * Math.cos(yaw) - point.x * Math.sin(yaw);
  const y = point.y * Math.cos(pitch) - z * Math.sin(pitch);
  const depth = point.y * Math.sin(pitch) + z * Math.cos(pitch);
  const factor = (540 / (540 - depth)) * zoom;
  return {
    x: width / 2 + x * factor,
    y: height / 2 + y * factor,
    depth,
    radius: Math.max(3, Math.min(10, 5 * factor)),
  };
}
function distanceToSegment(x: number, y: number, a: Point, b: Point) {
  const dx = b.x - a.x,
    dy = b.y - a.y;
  const t = Math.max(
    0,
    Math.min(1, ((x - a.x) * dx + (y - a.y) * dy) / (dx * dx + dy * dy || 1)),
  );
  return Math.hypot(x - (a.x + t * dx), y - (a.y + t * dy));
}

export function NetworkGraph3D({
  graph,
  dossier,
}: {
  graph: NetworkView;
  dossier: OfficerCaseView;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const projected = useRef<Map<string, Point>>(new Map());
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const [yaw, setYaw] = useState(0.35);
  const [pitch, setPitch] = useState(-0.2);
  const [zoom, setZoom] = useState(1);
  const [search, setSearch] = useState("");
  const [fromMonth, setFromMonth] = useState("");
  const [toMonth, setToMonth] = useState("");
  const [minimum, setMinimum] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [selected, setSelected] = useState<{ node?: Node; edge?: Edge } | null>(
    null,
  );
  const sourceNodes = useMemo(
    () => new Map(graph.nodes.map((node) => [node.node_id, node])),
    [graph.nodes],
  );
  const filtered = useMemo(() => {
    const reviewTransactions = new Set(
      dossier.findings
        .filter(
          (finding) =>
            finding.status === "UNRESOLVED" && finding.transaction_id,
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
    const companyMatches = new Set(
      graph.nodes
        .filter(
          (node) =>
            node.kind === "COMPANY" &&
            node.label
              .toLocaleLowerCase("fr")
              .includes(search.toLocaleLowerCase("fr")),
        )
        .map((node) => node.node_id),
    );
    const searchNodes = new Set(companyMatches);
    if (search.trim())
      for (const edge of graph.edges)
        if (
          companyMatches.has(edge.source) ||
          companyMatches.has(edge.target)
        ) {
          searchNodes.add(edge.source);
          searchNodes.add(edge.target);
        }
    const threshold = Number(minimum) * 1000;
    const nodes = graph.nodes.filter((node) => {
      if (reviewOnly && !reviewNodes.has(node.node_id)) return false;
      if (search.trim() && !searchNodes.has(node.node_id)) return false;
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
  }, [
    graph,
    dossier.case_id,
    dossier.findings,
    search,
    fromMonth,
    toMonth,
    minimum,
    reviewOnly,
  ]);

  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    let context: CanvasRenderingContext2D | null = null;
    try {
      context = element.getContext("2d");
    } catch {
      return;
    }
    if (!context) return;
    const draw = () => {
      const rect = element.getBoundingClientRect();
      const width = Math.max(1, rect.width),
        height = Math.max(1, rect.height);
      const scale = window.devicePixelRatio || 1;
      element.width = Math.round(width * scale);
      element.height = Math.round(height * scale);
      context!.setTransform(scale, 0, 0, scale, 0, 0);
      context!.clearRect(0, 0, width, height);
      context!.fillStyle = "#081a2d";
      context!.fillRect(0, 0, width, height);
      const points = new Map<string, Point>();
      filtered.nodes.forEach((node, index) => {
        const point = project(
          position(index, filtered.nodes.length),
          width,
          height,
          yaw,
          pitch,
          zoom,
        );
        points.set(node.node_id, { id: node.node_id, ...point });
      });
      projected.current = points;
      context!.lineWidth = 1;
      for (const edge of filtered.edges) {
        const a = points.get(edge.source),
          b = points.get(edge.target);
        if (!a || !b) continue;
        context!.beginPath();
        context!.moveTo(a.x, a.y);
        context!.lineTo(b.x, b.y);
        context!.strokeStyle =
          selected?.edge?.edge_id === edge.edge_id ? "#fff" : "#52728b88";
        context!.stroke();
      }
      for (const point of [...points.values()].sort(
        (a, b) => a.depth - b.depth,
      )) {
        const node = sourceNodes.get(point.id)!;
        context!.beginPath();
        context!.arc(point.x, point.y, point.radius, 0, Math.PI * 2);
        context!.fillStyle = colors[node.kind] || "#c0d9e5";
        context!.fill();
        if (selected?.node?.node_id === point.id) {
          context!.strokeStyle = "#fff";
          context!.lineWidth = 2;
          context!.stroke();
        }
        if (node.kind === "COMPANY" || selected?.node?.node_id === point.id) {
          context!.fillStyle = "#e5f5f7";
          context!.font = "11px sans-serif";
          context!.fillText(
            node.label.slice(0, 27),
            point.x + point.radius + 4,
            point.y + 3,
          );
        }
      }
    };
    const observer = new ResizeObserver(draw);
    observer.observe(element);
    draw();
    return () => observer.disconnect();
  }, [filtered, yaw, pitch, zoom, selected, sourceNodes]);

  const pick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (drag.current?.moved) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const x = event.clientX - rect.left,
      y = event.clientY - rect.top;
    const near = [...projected.current.values()].sort(
      (a, b) => Math.hypot(a.x - x, a.y - y) - Math.hypot(b.x - x, b.y - y),
    )[0];
    if (near && Math.hypot(near.x - x, near.y - y) < near.radius + 6) {
      setSelected({ node: sourceNodes.get(near.id) });
      return;
    }
    const edge = filtered.edges.find((item) => {
      const a = projected.current.get(item.source),
        b = projected.current.get(item.target);
      return a && b && distanceToSegment(x, y, a, b) < 5;
    });
    setSelected(edge ? { edge } : null);
  };
  const selectedCompany =
    selected?.node?.kind === "COMPANY" ? selected.node : null;
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
    if (
      !invoice ||
      !invoice.attributes.currency ||
      !invoice.attributes.gross_millimes
    )
      continue;
    invoiceTotals.set(
      invoice.attributes.currency,
      (invoiceTotals.get(invoice.attributes.currency) ?? 0) +
        Number(invoice.attributes.gross_millimes),
    );
  }
  const relatedFindings =
    selected?.edge?.case_id === dossier.case_id
      ? dossier.findings.filter(
          (finding) =>
            finding.status === "UNRESOLVED" &&
            finding.transaction_id &&
            selected.edge!.source_ids.includes(finding.transaction_id),
        )
      : null;
  return (
    <section className="network-3d" aria-label="Graphe 3D du réseau">
      <div className="network-controls">
        <label>
          Rechercher une entreprise
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Nom de l’entreprise"
          />
        </label>
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
        <button
          className="secondary"
          onClick={() => setZoom((value) => Math.min(2.5, value * 1.2))}
        >
          Zoom +
        </button>
        <button
          className="secondary"
          onClick={() => setZoom((value) => Math.max(0.4, value / 1.2))}
        >
          Zoom −
        </button>
      </div>
      <p>
        {filtered.nodes.length} nœuds · {filtered.edges.length} relations
        affichées
      </p>
      <canvas
        ref={canvas}
        aria-label="Réseau 3D rotatif ; glisser pour tourner, molette pour zoomer, cliquer pour sélectionner"
        role="img"
        onPointerDown={(event) => {
          drag.current = { x: event.clientX, y: event.clientY, moved: false };
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          const dx = event.clientX - drag.current.x,
            dy = event.clientY - drag.current.y;
          if (Math.abs(dx) + Math.abs(dy) > 3) drag.current.moved = true;
          setYaw((value) => value + dx * 0.006);
          setPitch((value) =>
            Math.max(-1.4, Math.min(1.4, value + dy * 0.006)),
          );
          drag.current.x = event.clientX;
          drag.current.y = event.clientY;
        }}
        onPointerUp={(event) => {
          pick(event);
          drag.current = null;
        }}
        onWheel={(event) => {
          event.preventDefault();
          setZoom((value) =>
            Math.max(
              0.4,
              Math.min(2.5, value * (event.deltaY < 0 ? 1.08 : 0.92)),
            ),
          );
        }}
      />
      <div className="network-selection" aria-live="polite">
        {selected?.node ? (
          <>
            <strong>{selected.node.label}</strong>
            <p>
              {selected.node.kind} · {selected.node.case_ids.length} dossier(s)
            </p>
            {selectedCompany && (
              <>
                <p>
                  {linkedInvoices.length} observations de facture liées ·{" "}
                  {selectedCompany.case_ids.length} dossiers liés
                </p>
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
        ) : selected?.edge ? (
          <>
            <strong>
              {sourceNodes.get(selected.edge.source)?.label ??
                selected.edge.source}{" "}
              ↔{" "}
              {sourceNodes.get(selected.edge.target)?.label ??
                selected.edge.target}
            </strong>
            <p>
              {selected.edge.kind} · dossier {selected.edge.case_id}
            </p>
            <small>
              Sources : {selected.edge.source_ids.join(", ")} ·{" "}
              {selected.edge.provenance_status}
            </small>
            <p>
              {selected.edge.source_ids.length} références ·{" "}
              {relatedFindings === null
                ? "écarts de cet autre dossier non chargés"
                : `${relatedFindings.length} constats actifs du dossier courant`}{" "}
              · comparaison historique du lien non disponible
            </p>
          </>
        ) : (
          <p>Sélectionnez un nœud ou une relation pour voir ses sources.</p>
        )}
      </div>
      <details>
        <summary>Liste accessible des nœuds visibles</summary>
        <div className="network-edge-list">
          {filtered.nodes.map((node) => (
            <button
              key={node.node_id}
              className="secondary"
              onClick={() => setSelected({ node })}
            >
              {node.kind} · {node.label}
            </button>
          ))}
        </div>
      </details>
      <details>
        <summary>Liste accessible des relations visibles</summary>
        <div className="network-edge-list">
          {filtered.edges.map((edge) => (
            <button
              key={edge.edge_id}
              className="secondary"
              onClick={() => setSelected({ edge })}
            >
              {sourceNodes.get(edge.source)?.label ?? edge.source} →{" "}
              {sourceNodes.get(edge.target)?.label ?? edge.target} · {edge.kind}
            </button>
          ))}
        </div>
      </details>
      <p className="footnote">
        La position des nœuds sert seulement à explorer le graphe. Les filtres
        de période et de montant portent sur les faits datés et chiffrés ; les
        constats affichés concernent le dossier courant.
      </p>
    </section>
  );
}
