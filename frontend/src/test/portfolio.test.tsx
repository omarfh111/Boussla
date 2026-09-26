import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
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
  Finding,
  HistoryView,
  Hypothesis,
  InvestigatorBrief,
  InvoiceObservation,
  OfficerCaseView,
  QueueItem,
} from "../api/types";

const queue: QueueItem[] = [
  {
    case_id: "C-A",
    company_id: "E-A",
    company_display_name: "Atelier Alpha",
    case_version: 2,
    review_index: 20,
    evidence_coverage: "50",
    coverage_complete: false,
    active_finding_count: 1,
    clarification_status: "PUBLISHED_IN_DEMO",
    scope_note: "Synthétique",
    sector: "Industrie",
    synthetic_identifier: "SYN-A",
    triage: { rank: 1, level: "NORMAL", label_fr: "Normal" },
    last_activity_at: "2026-09-01T10:00:00Z",
    historical_signals: [],
    history_anomaly: false,
  },
  {
    case_id: "C-B",
    company_id: "E-B",
    company_display_name: "Bâtiment Beta",
    case_version: 3,
    review_index: 40,
    evidence_coverage: "100",
    coverage_complete: true,
    active_finding_count: 2,
    clarification_status: "NOT_REQUESTED",
    scope_note: "Synthétique",
    sector: "Construction",
    synthetic_identifier: "SYN-B",
    triage: { rank: 3, level: "HIGH", label_fr: "Élevé" },
    last_activity_at: "2026-09-03T10:00:00Z",
    historical_signals: [
      { label_fr: "Variation documentée", status: "REVIEW" },
    ],
    history_anomaly: true,
  },
  {
    case_id: "C-C",
    company_id: "E-C",
    company_display_name: "Commerce Gamma",
    case_version: 1,
    review_index: 10,
    evidence_coverage: null,
    coverage_complete: null,
    active_finding_count: 0,
    clarification_status: "NOT_REQUESTED",
    scope_note: "Synthétique",
    sector: "Commerce",
    synthetic_identifier: "SYN-C",
    triage: null,
    last_activity_at: null,
    historical_signals: [],
    history_anomaly: null,
  },
];
afterEach(cleanup);

it("shows a multi-enterprise portfolio and selects the exact case", () => {
  const open = vi.fn();
  render(<Portfolio items={queue} onOpen={open} />);
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
  expect(screen.getAllByText("Triage / urgence").length).toBeGreaterThan(0);
  expect(
    screen.getAllByText("Priorité de revue déterministe").length,
  ).toBeGreaterThan(0);
  fireEvent.click(screen.getByRole("button", { name: "Ouvrir Bâtiment Beta" }));
  expect(open).toHaveBeenCalledWith("C-B");
  expect(document.body.textContent).not.toMatch(
    /probabilit[ée] de fraude|fraud probability/i,
  );
});

it("searches, sorts, and filters only on supplied portfolio fields", () => {
  expect(
    selectPortfolio(queue, "", "all", "", "review").map((x) => x.case_id),
  ).toEqual(["C-B", "C-A", "C-C"]);
  expect(
    selectPortfolio(queue, "", "highest-triage", "", "triage").map(
      (x) => x.case_id,
    ),
  ).toEqual(["C-B"]);
  expect(
    selectPortfolio(queue, "", "clarification-pending", "", "review").map(
      (x) => x.case_id,
    ),
  ).toEqual(["C-A"]);
  expect(
    selectPortfolio(queue, "", "evidence-incomplete", "", "review").map(
      (x) => x.case_id,
    ),
  ).toEqual(["C-A"]);
  expect(
    selectPortfolio(queue, "", "history-anomaly", "", "review").map(
      (x) => x.case_id,
    ),
  ).toEqual(["C-B"]);
  expect(
    selectPortfolio(queue, "syn-c", "all", "Commerce", "review").map(
      (x) => x.case_id,
    ),
  ).toEqual(["C-C"]);
  render(<Portfolio items={queue} onOpen={() => {}} />);
  fireEvent.change(
    screen.getByPlaceholderText("Rechercher une entreprise ou un dossier"),
    { target: { value: "Atelier" } },
  );
  expect(
    within(screen.getByRole("list")).getAllByRole("listitem"),
  ).toHaveLength(1);
});

const observation: InvoiceObservation = {
  document_id: "DOC-BUY",
  transaction_id: "TX-1",
  perspective: "BUYER_RECEIVED",
  issuer_company_id: "SELLER-1",
  buyer_company_id: "BUYER-1",
  invoice_number: "FAC-001",
  issued_on: "2026-09-02",
  currency: "TND",
  net_millimes: 100000,
  tax_millimes: 19000,
  gross_millimes: 119000,
  origin_group_id: "BUYER-UPLOAD",
  lines: [
    {
      line_id: "L1",
      item_description: "Matériau",
      quantity: "10",
      unit: "pièce",
    },
  ],
};
const matchingFinding: Finding = {
  finding_id: "F-MATCH",
  family: "COUNTERPARTY",
  status: "EXPLAINED",
  reason_code: "INDEPENDENT_INVOICE_VIEWS_MATCH",
  quantity_difference: null,
  unit: null,
  calculation_version: "v1",
  evidence_refs: [],
  missing_evidence_types: [],
};

it("compares buyer and seller fields, with highlights only from the backend comparison", () => {
  const seller: InvoiceObservation = {
    ...observation,
    document_id: "DOC-SELL",
    perspective: "SELLER_ISSUED",
    origin_group_id: "SELLER-FEED",
  };
  const { rerender } = render(
    <InvoiceCompare
      observations={[observation, seller]}
      finding={matchingFinding}
      comparison={null}
    />,
  );
  expect(screen.getByText(/Observations concordantes/)).toBeInTheDocument();
  expect(screen.getAllByText("FAC-001")).toHaveLength(2);
  expect(screen.getByText("BUYER-UPLOAD")).toBeInTheDocument();
  expect(screen.getByText("SELLER-FEED")).toBeInTheDocument();
  expect(document.querySelectorAll(".comparison-difference")).toHaveLength(0);
  rerender(
    <InvoiceCompare
      observations={[observation, seller]}
      finding={{
        ...matchingFinding,
        reason_code: "AMOUNT_MISMATCH",
        status: "UNRESOLVED",
      }}
      comparison={{
        status: "DIFFERENT",
        reason_code: "AMOUNT_MISMATCH",
        difference_fields: ["gross_millimes"],
      }}
    />,
  );
  expect(document.querySelectorAll(".comparison-difference")).toHaveLength(2);
  rerender(
    <InvoiceCompare
      observations={[
        observation,
        seller,
        {
          ...observation,
          document_id: "DOC-BUY-2",
          transaction_id: "TX-2",
          invoice_number: "FAC-002",
        },
      ]}
      finding={{
        ...matchingFinding,
        reason_code: "AMOUNT_MISMATCH",
        status: "UNRESOLVED",
      }}
      comparison={{
        status: "DIFFERENT",
        reason_code: "AMOUNT_MISMATCH",
        difference_fields: ["gross_millimes"],
      }}
    />,
  );
  expect(document.querySelectorAll(".comparison-difference")).toHaveLength(0);
  expect(
    screen.queryByText(/Observations concordantes/),
  ).not.toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(
    /déclaration valide|valid declaration/i,
  );
});

const officer: OfficerCaseView = {
  audience: "OFFICER",
  case_id: "C-A",
  company_id: "E-A",
  company_display_name: "Atelier Alpha",
  case_version: 2,
  documents: [],
  transactions: [
    {
      transaction_id: "TX-1",
      counterparty_display_name: "Vendeur synthétique",
      invoice_number: "FAC-001",
      issued_on: "2026-09-02",
      invoiced_gross_millimes: 119000,
      settled_millimes: 119000,
      declared_millimes: null,
      corroboration_status: "MATCH",
      project_id: null,
    },
  ],
  projects: [],
  context_claims: [
    {
      claim_id: "CLAIM-1",
      purpose_category: "LONG_LIVED_ASSET",
      purpose_text: "Véhicule de service déclaré",
      beneficiary_type: "Entreprise",
      planned_start: null,
      planned_end: null,
      stage: null,
      submitted_at: "2026-09-03T10:00:00Z",
      declared_horizon: "UNKNOWN",
      supersedes_claim_id: null,
    },
  ],
  allocations: [],
  context_assessment: null,
  mode: "LIVE",
  banner_fr: "Données synthétiques",
  score: null,
  findings: [matchingFinding],
  hypotheses: [],
  scenarios: [],
  requests: [],
  responses: [],
  proposals: [],
  candidate_passages: [],
  reference_note: null,
  mode_by_node: {},
  invoice_observations: [observation],
  quantity_references: [],
  enterprise_profile: {
    display_name: "Atelier Alpha",
    sector: "Industrie",
    synthetic_identifier: "SYN-A",
    activity_period: { start: "2026-01-01", end: "2026-09-30" },
  },
  payment_timeline: [
    {
      payment_id: "PAY-1",
      occurred_at: "2026-09-04",
      amount_millimes: 119000,
      currency: "TND",
      status: "SETTLED",
      origin_group_id: "SYNTHETIC-LEDGER",
    },
  ],
  monthly_activity: [
    {
      month: "2026-09",
      transaction_count: 1,
      inflow_millimes: null,
      outflow_millimes: 119000,
      source_label: "Journal synthétique",
    },
  ],
  financial_activity: {
    observed_settlements_millimes: 119000,
    inflow_millimes: null,
    outflow_millimes: 119000,
    currency: "TND",
    source_label: "Journal synthétique",
  },
};
const history: HistoryView = {
  revisions: [
    {
      version: 1,
      parent_version: null,
      reason: "Création",
      created_at: "2026-09-01T10:00:00Z",
    },
    {
      version: 2,
      parent_version: 1,
      reason: "Contexte reçu",
      created_at: "2026-09-03T10:00:00Z",
    },
  ],
  events: [],
};

it("renders Company 360 profile, histories, monthly activity and synthetic financial provenance", () => {
  render(<Company360 c={officer} history={history} />);
  expect(screen.getByText("Industrie")).toBeInTheDocument();
  expect(screen.getByText("SYN-A")).toBeInTheDocument();
  expect(screen.getAllByText("FAC-001").length).toBeGreaterThan(0);
  expect(screen.getByText("2026-09")).toBeInTheDocument();
  expect(screen.getByText("Contexte reçu")).toBeInTheDocument();
  expect(screen.getByText("Véhicule de service déclaré")).toBeInTheDocument();
  expect(screen.getAllByText(/Journal synthétique/).length).toBeGreaterThan(0);
  expect(document.body.textContent).not.toMatch(/banque réelle|real.bank/i);
});

const hypotheses: Hypothesis[] = Array.from({ length: 6 }, (_, index) => ({
  hypothesis_id: `H-${index}`,
  name_fr: `Hypothèse ${index}`,
  status: "UNRESOLVED",
  scope: "TX-1",
  support_index: index,
  supporting_refs: [
    { document_id: "DOC-BUY", source_record_id: null, page: null },
  ],
  contradicting_refs: [],
  missing_evidence_types: ["STOCK_RECORD"],
}));

it("shows at most five hypotheses and labels the supplied support index", () => {
  render(<HypothesisCards hypotheses={hypotheses} />);
  expect(screen.getAllByText(/Hypothèse [0-4]/)).toHaveLength(5);
  expect(screen.queryByText("Hypothèse 5")).not.toBeInTheDocument();
  expect(screen.getAllByText("Support de l’hypothèse")).toHaveLength(5);
  expect(screen.getAllByText("DOC-BUY")).toHaveLength(5);
});

it("renders every InvestigatorBrief section and an honest missing-contract state", () => {
  const brief: InvestigatorBrief = {
    summary_fr: "Résumé fourni.",
    key_observations: [{ text_fr: "Observation fournie.", evidence_refs: [] }],
    top_hypotheses: hypotheses.slice(0, 1),
    missing_information: ["Pièce manquante"],
    changes_since_last_version: ["Nouvelle réponse"],
    questions_proposed: ["Question à poser"],
    questions_already_asked: ["Question posée"],
    candidate_public_references: [
      {
        rule_id: "R-1",
        document_title: "Référence candidate",
        text: "Passage",
        source_url: "https://example.org/",
        page: null,
        article: null,
        mode: "LIVE",
      },
    ],
    mode: "LIVE",
  };
  const { rerender } = render(<InvestigatorPanel brief={brief} />);
  for (const title of [
    "Résumé",
    "Observations clés",
    "Top hypothèses",
    "Informations manquantes",
    "Changements depuis la dernière version",
    "Questions proposées / déjà posées",
    "Références publiques candidates",
  ])
    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
  expect(screen.getByText("Résumé fourni.")).toBeInTheDocument();
  rerender(<InvestigatorPanel brief={null} />);
  expect(
    screen.getByText(/n’a pas fourni d’InvestigatorBrief/),
  ).toBeInTheDocument();
  expect(screen.queryByText("Résumé fourni.")).not.toBeInTheDocument();
});

it("renders scenario cards using backend values and keeps the simulation disclaimer", () => {
  render(
    <ScenarioCards
      reviewIndex={40}
      scenarios={[
        {
          scenario_id: "S-1",
          label: "Si affectation P2 acceptée",
          outputs: { review_index: 0 },
        },
        {
          scenario_id: "S-2",
          label: "Si seulement 500 unités expliquées",
          outputs: { review_index: 20 },
        },
      ]}
    />,
  );
  expect(screen.getByText("Priorité 40")).toBeInTheDocument();
  expect(screen.getByText("Si affectation P2 acceptée")).toBeInTheDocument();
  expect(
    screen.getByText("Si seulement 500 unités expliquées"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Simulation hypothétique — aucun changement du dossier."),
  ).toBeInTheDocument();
  expect(screen.getByText("0")).toBeInTheDocument();
  expect(screen.getByText("20")).toBeInTheDocument();
});

it("keeps demo administration actions disabled without authorized endpoints", () => {
  render(<DemoAdmin items={queue} />);
  expect(screen.getByText("DONNÉES SYNTHÉTIQUES")).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Supprimer" })).toHaveLength(3);
  for (const button of screen.getAllByRole("button"))
    expect(button).toBeDisabled();
});
