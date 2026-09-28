import { afterEach, expect, it } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Company360,
  DemoAdmin,
  HypothesisCards,
  InvestigatorPanel,
  InvoiceCompare,
  Portfolio,
  ScenarioCards,
  selectPortfolio,
} from "../portfolio/components";
import type {
  BriefHypothesis,
  InvestigatorBrief,
  InvoiceObservation,
  OfficerCaseView,
  QueueItem,
} from "../api/types";

const row = (over: Partial<QueueItem>): QueueItem => ({
  case_id: "C",
  company_id: "E",
  company_display_name: "Entreprise",
  case_version: 1,
  review_index: 0,
  evidence_coverage: "100.00",
  coverage_complete: true,
  active_finding_count: 0,
  clarification_status: "NOT_REQUESTED",
  scope_note: "Synthétique",
  triage_priority: 0,
  triage_reason_codes: [],
  sector: "Services",
  synthetic_identifier: "SYNTHETIC-MF-X",
  last_activity_at: "2025-12-10",
  history_signal_codes: [],
  history_anomaly: false,
  ...over,
});
// Server order: triage desc (the UI must keep it for "triage").
const queue: QueueItem[] = [
  row({
    case_id: "SYN-OP-012-CASE",
    company_display_name: "SYNTHÉTIQUE — Travaux Opale",
    sector: "Construction",
    review_index: 67,
    triage_priority: 82,
    triage_reason_codes: [
      "REVIEW_FINDING_PRESENT",
      "TRANSACTION_INCONSISTENCY_NEEDS_REVIEW",
    ],
    history_signal_codes: ["REPEATED_INVOICE_CONFLICT"],
    history_anomaly: true,
    active_finding_count: 3,
  }),
  row({
    case_id: "CASE-BRICKS-001",
    company_display_name: "Bâtisseur Démo",
    sector: "Construction",
    review_index: 40,
    triage_priority: 40,
    clarification_status: "PENDING",
    history_anomaly: null,
    coverage_complete: false,
  }),
  row({
    case_id: "SYN-OP-005-CASE",
    company_display_name: "SYNTHÉTIQUE — Fournitures Dune",
    sector: "Distribution",
    review_index: 0,
    triage_priority: 25,
    triage_reason_codes: ["ACTIVITY_GAP_NEEDS_REVIEW"],
    history_signal_codes: ["ACTIVITY_GAP"],
    history_anomaly: true,
    last_activity_at: "2025-12-15",
  }),
];

afterEach(cleanup);

it("keeps the authoritative triage order and shows triage separately from the index", () => {
  render(<Portfolio items={queue} onOpen={() => {}} />);
  const cards = Array.from(document.querySelectorAll(".portfolio-card-item"));
  expect(
    cards.map(
      (c) =>
        within(c as HTMLElement).getByText(/SYNTHÉTIQUE|Bâtisseur/).textContent,
    ),
  ).toEqual([
    "SYNTHÉTIQUE — Travaux Opale",
    "Bâtisseur Démo",
    "SYNTHÉTIQUE — Fournitures Dune",
  ]);
  expect(
    within(cards[0] as HTMLElement).getByText("82", {
      selector: ".portfolio-triage",
    }),
  ).toBeInTheDocument();
  expect(
    within(cards[0] as HTMLElement).getByText("67", {
      selector: ".portfolio-index",
    }),
  ).toBeInTheDocument();
  fireEvent.click(
    within(cards[2] as HTMLElement).getByText(/Motif · Période sans activité/),
  );
  expect(
    within(cards[2] as HTMLElement).getByText(
      "Période sans activité à examiner",
      { selector: "li" },
    ),
  ).toBeVisible();
  expect(document.body.textContent).not.toMatch(
    /fraude détectée|activité suspecte|entreprise frauduleuse/i,
  );
});

it("searches, sorts and filters only on server-supplied fields", () => {
  expect(
    selectPortfolio(queue, "dune", "all", "", "triage").map((i) => i.case_id),
  ).toEqual(["SYN-OP-005-CASE"]);
  expect(
    selectPortfolio(queue, "", "all", "", "review").map((i) => i.review_index),
  ).toEqual([67, 40, 0]);
  expect(
    selectPortfolio(queue, "", "highest-triage", "", "triage"),
  ).toHaveLength(1);
  expect(
    selectPortfolio(queue, "", "history-anomaly", "", "triage"),
  ).toHaveLength(2);
  expect(
    selectPortfolio(queue, "", "clarification-pending", "", "triage"),
  ).toHaveLength(1);
  expect(
    selectPortfolio(queue, "", "evidence-incomplete", "", "triage"),
  ).toHaveLength(1);
  expect(
    selectPortfolio(queue, "", "all", "Distribution", "triage"),
  ).toHaveLength(1);
  const onOpen = (id: string) => opened.push(id);
  const opened: string[] = [];
  render(<Portfolio items={queue} onOpen={onOpen} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Ouvrir Bâtisseur Démo" }),
  );
  expect(opened).toEqual(["CASE-BRICKS-001"]);
});

const obs = (
  id: string,
  perspective: string,
  over: Partial<InvoiceObservation> = {},
): InvoiceObservation => ({
  observation_id: id,
  document_id: `DOC-${id}`,
  transaction_id: "TX-1",
  perspective,
  issuer_company_id: "SELLER",
  buyer_company_id: "BUYER",
  invoice_number: "FAC-1",
  invoice_version: "1",
  issued_on: "2025-03-10",
  currency: "TND",
  net_millimes: 1000000,
  tax_millimes: 190000,
  gross_millimes: 1190000,
  origin_group_id:
    perspective === "BUYER_RECEIVED" ? "COMPANY-BUYER" : "SELLER-RECORDS",
  lines: [
    {
      line_id: "L1",
      item_description: "Unités",
      quantity: "100",
      unit: "pièce",
      unit_price_millimes: 10000,
      line_net_millimes: 1000000,
    },
  ],
  ...over,
});

it("compares buyer/seller pairs and highlights only backend difference fields", () => {
  const observations = [
    obs("B1", "BUYER_RECEIVED"),
    obs("S1", "SELLER_ISSUED", {
      lines: [
        {
          line_id: "L1",
          item_description: "Unités",
          quantity: "80",
          unit: "pièce",
          unit_price_millimes: 12500,
          line_net_millimes: 1000000,
        },
      ],
    }),
    obs("B2", "BUYER_RECEIVED", { transaction_id: "TX-2" }),
    obs("S2", "SELLER_ISSUED", { transaction_id: "TX-2" }),
  ];
  render(
    <InvoiceCompare
      observations={observations}
      comparisons={[
        {
          transaction_id: "TX-2",
          buyer_observation_id: "B2",
          seller_observation_id: "S2",
          status: "CONCORDANT",
          label_fr: "Observations concordantes",
          difference_fields: [],
          counterparty_reason_code: null,
        },
        {
          transaction_id: "TX-1",
          buyer_observation_id: "B1",
          seller_observation_id: "S1",
          status: "DIFFERENCES",
          label_fr: "Différences observées entre les deux observations",
          difference_fields: ["line.quantity", "line.unit_price_millimes"],
          counterparty_reason_code: null,
        },
      ]}
    />,
  );
  const highlighted = document.querySelectorAll(".comparison-difference dt");
  expect([...highlighted].map((n) => n.textContent)).toEqual([
    "Quantité",
    "Prix unitaire",
    "Quantité",
    "Prix unitaire",
  ]);
  expect(
    screen.getByText("Différences observées entre les deux observations"),
  ).toBeInTheDocument();
  expect(screen.getByText("Observations concordantes")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(
    /Déclaration validée|Facture authentique|Conformité prouvée/,
  );
});

const officer = {
  audience: "OFFICER",
  case_id: "SYN-OP-005-CASE",
  company_id: "SYN-OP-005",
  company_display_name: "SYNTHÉTIQUE — Fournitures Dune",
  case_version: 1,
  documents: [],
  transactions: [
    {
      transaction_id: "TX-1",
      counterparty_display_name: null,
      invoice_number: "FAC-1",
      issued_on: "2025-01-10",
      invoiced_gross_millimes: 1190000,
      settled_millimes: 1190000,
      declared_millimes: null,
      corroboration_status: "DISTINCT_RECORDED_ORIGINS_NOT_AUTHENTICITY",
      project_id: null,
    },
  ],
  projects: [],
  context_claims: [],
  allocations: [],
  context_assessment: null,
  mode: "LIVE",
  banner_fr: "",
  score: null,
  findings: [],
  hypotheses: [],
  scenarios: [],
  requests: [],
  responses: [],
  proposals: [],
  candidate_passages: [],
  reference_note: null,
  mode_by_node: {},
  invoice_observations: [
    obs("B1", "BUYER_RECEIVED"),
    obs("S1", "SELLER_ISSUED"),
  ],
  invoice_comparisons: [
    {
      transaction_id: "TX-1",
      buyer_observation_id: "B1",
      seller_observation_id: "S1",
      status: "CONCORDANT",
      label_fr: "Observations concordantes",
      difference_fields: [],
      counterparty_reason_code: null,
    },
  ],
  investigator_brief: null,
  triage: null,
  clarification_deadlines: [],
  history_signals: [
    {
      signal_id: "SIG-1",
      company_id: "SYN-OP-005",
      reason_code: "ACTIVITY_GAP",
      period: "2025-09/2025-10",
      metric: "consecutive_covered_zero_activity_months",
      observed_value: "2",
      baseline_value: "0",
      baseline_periods: [],
      evidence_source_ids: ["SRC-1"],
      explanation_fr:
        "Aucune transaction dans ces mois couverts du jeu synthétique.",
      method: "SYNTHETIC_HISTORY_V1",
      mode: "LIVE",
      affects_review_index: false,
    },
  ],
  enterprise_profile: {
    company_id: "SYN-OP-005",
    display_name: "SYNTHÉTIQUE — Fournitures Dune",
    synthetic_identifier: "SYNTHETIC-MF-OP-005",
    sector: "Distribution",
    created_on: "2024-01-01",
    activity_start: "2025-01",
    activity_end: "2025-12",
    portfolio_member: true,
    data_kind: "SYNTHETIC",
  },
  monthly_activity: [
    {
      month: "2025-01",
      transaction_count: 1,
      invoice_observation_count: 2,
      settled_outflow_millimes: 1190000,
      source_label: "Faits synthétiques du dossier",
      coverage_status: "COVERED",
      coverage_source_id: "COV-2025-01",
    },
    {
      month: "2025-11",
      transaction_count: 2,
      invoice_observation_count: 4,
      settled_outflow_millimes: 2380000,
      source_label: "Faits synthétiques du dossier",
      coverage_status: "COVERED",
      coverage_source_id: "COV-2025-11",
    },
  ],
  payment_timeline: [
    {
      payment_id: "PAY-1",
      transaction_id: "TX-1",
      occurred_at: "2025-01-20T00:00:00Z",
      amount_millimes: 1190000,
      currency: "TND",
      status: "SETTLED",
      origin_group_id: "BANK-SYN",
    },
  ],
  financial_snapshot: {
    label_fr: "Instantané financier synthétique — source autorisée simulée",
    data_kind: "SYNTHETIC",
    as_of: "2026-01-10T00:00:00Z",
    currency: "TND",
    observed_outflows_millimes: 1190000,
    observed_settlements_millimes: 1190000,
    documented_payable_millimes: 1190000,
    outstanding_documented_payable_millimes: 0,
    inflows_millimes: null,
    scope: "GENERATED_PURCHASE_LEDGER_ONLY",
    statement_fr:
      "Contexte synthétique autorisé pour la démo uniquement ; aucune connexion bancaire.",
    source_count: 2,
  },
  quantity_references: [],
  history_signal_index: null,
  history_signal_status: "INSUFFICIENT_DATA",
  history_signal_factors: [],
  history_signal_method: null,
  operational_confidence_index: null,
  operational_confidence_status: "INSUFFICIENT_DATA",
  operational_confidence_as_of: "2026-09-27T00:00:00Z",
  operational_confidence_factors: [],
  operational_confidence_eligible_observations: 0,
  operational_confidence_method: "OPERATIONAL_CONFIDENCE_V2",
} satisfies OfficerCaseView;

it("renders Company 360 from server data with synthetic, neutral provenance", () => {
  render(
    <Company360
      c={officer}
      history={{
        revisions: [
          {
            version: 1,
            parent_version: null,
            reason: "Portefeuille synthétique",
            created_at: "2026-09-26T00:00:00Z",
          },
        ],
        events: [],
      }}
    />,
  );
  expect(screen.getByText("SYNTHETIC-MF-OP-005")).toBeInTheDocument();
  expect(screen.getByText("2025-01 — 2025-12")).toBeInTheDocument();
  expect(
    screen.getByText(
      "Instantané financier synthétique — source autorisée simulée",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Période sans activité documentée"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/ni des constats ni des indices de fraude/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Non fournies (périmètre achats uniquement)"),
  ).toBeInTheDocument();
  expect(
    screen.getAllByRole("listitem", { name: undefined }).length,
  ).toBeGreaterThan(0);
  expect(document.body.textContent).not.toMatch(
    /solde bancaire|compte bancaire réel/i,
  );
});

const hyp = (id: string, n: number): BriefHypothesis => ({
  hypothesis_id: id,
  name_fr: `Hypothèse ${n}`,
  status: "INSUFFICIENT",
  supporting_refs: n === 1 ? ["DOC-REF-001"] : [],
  contradicting_refs: [],
  missing_evidence: ["ALLOCATION_RESPONSE"],
  why_it_matters_fr: "Explication neutre.",
});

it("shows at most five catalogue hypotheses with a support label, never a probability", () => {
  render(
    <HypothesisCards
      hypotheses={[1, 2, 3, 4, 5, 6].map((n) => hyp(`H${n}`, n))}
    />,
  );
  expect(screen.getAllByRole("article")).toHaveLength(5);
  expect(screen.getAllByText(/Support de l’hypothèse/)).toHaveLength(5);
  expect(screen.getByText("DOC-REF-001")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(
    /Probabilité de fraude\s*:|fraude détectée/i,
  );
});

it("renders every investigator section with the permanent statement", () => {
  const brief: InvestigatorBrief = {
    case_id: "C",
    case_version: 2,
    summary_fr: "Synthèse indicative.",
    key_observations: [
      {
        kind: "FACT",
        text_fr: "Historique synthétique observé (2025-09/2025-10) : pause.",
        source_codes: [],
      },
    ],
    top_hypotheses: [hyp("SECOND_PROJECT_ALLOCATION", 1)],
    missing_information: ["ALLOCATION_RESPONSE"],
    changes_since_previous_version: [
      "QUANTITY TX-001 : UNRESOLVED → EXPLAINED",
    ],
    questions_proposed: ["Q-STOCK"],
    questions_already_asked: ["Q-PROJECT-ALLOCATION"],
    reference_rule_ids: ["TN-REF-1"],
    history_signal_codes: ["ACTIVITY_GAP"],
    limitations: ["Aucune conclusion juridique."],
    mode: "TEMPLATE",
    authoritative: false,
    label_fr: "Analyse assistée BOUSSLA",
    disclaimer_fr:
      "L'analyse assistée ne modifie pas l'indice de revue ni les faits du dossier.",
  };
  render(
    <InvestigatorPanel
      brief={brief}
      passages={[
        {
          rule_id: "TN-REF-1",
          document_title: "Référence publique",
          text: "",
          source_url: "",
          page: null,
          article: null,
          mode: "TEMPLATE",
        },
      ]}
    />,
  );
  for (const title of [
    "Résumé",
    "Observations clés",
    "Top hypothèses",
    "Informations manquantes",
    "Changements depuis la version précédente",
    "Questions proposées / déjà posées",
    "Références publiques candidates",
    "Limitations",
  ])
    expect(screen.getByText(title)).toBeInTheDocument();
  expect(screen.getByText("Analyse assistée BOUSSLA")).toBeInTheDocument();
  expect(
    screen.getByText(
      "L'analyse assistée ne modifie pas l'indice de revue ni les faits du dossier.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Proposée : Quantité conservée en stock"),
  ).toBeInTheDocument();
  expect(screen.getByText("Référence publique · TN-REF-1")).toBeInTheDocument();
  cleanup();
  render(<InvestigatorPanel brief={null} passages={[]} />);
  expect(screen.getByText(/Aucune analyse n’est simulée/)).toBeInTheDocument();
});

it("shows deterministic scenario outputs and never invents an index", () => {
  render(
    <ScenarioCards
      reviewIndex={40}
      scenarios={[
        {
          scenario_id: "TX-001:REALLOCATION:P2:v1",
          label: "Réaffectation hypothétique P1=1000 / P2=1000",
          inputs: {},
          outputs: {
            status: "HYPOTHETICAL",
            current_review_index: "40",
            hypothetical_review_index: "0",
            residual_units: "0",
            unit: "piece",
          },
          hypothetical: true,
        },
        {
          scenario_id: "TX-001:MARGIN:0.10:v1",
          label: "Marge hypothétique 10.00%",
          inputs: {},
          outputs: {
            status: "HYPOTHETICAL",
            residual_units: "900",
            unit: "piece",
          },
          hypothetical: true,
        },
      ]}
    />,
  );
  const [, realloc, margin] = screen.getAllByRole("article");
  expect(
    within(realloc).getByText("Indice de revue hypothétique"),
  ).toBeInTheDocument();
  expect(
    within(margin).queryByText("Indice de revue hypothétique"),
  ).not.toBeInTheDocument();
  expect(within(margin).getByText("900")).toBeInTheDocument();
  expect(
    screen.getByText("Simulation hypothétique — aucun changement du dossier."),
  ).toBeInTheDocument();
});

it("keeps administration unavailable without the operator capability", () => {
  const client = new QueryClient();
  render(
    <QueryClientProvider client={client}>
      <DemoAdmin enabled={false} />
    </QueryClientProvider>,
  );
  expect(
    screen.getByText("Réservé au rôle « Opérateur démo »."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Réinitialiser/ }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(
      "Administration de données synthétiques — démonstration locale.",
    ),
  ).toBeInTheDocument();
});
