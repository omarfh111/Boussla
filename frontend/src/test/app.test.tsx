import { afterEach, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../App";
import type { CompanyCaseView, OfficerCaseView } from "../api/types";

const shared = {
  case_id: "CASE-BRICKS-001",
  company_id: "DEMO-BAT",
  company_display_name: "Bâtiments Démo",
  case_version: 1,
  documents: [],
  transactions: [],
  projects: [
    { project_id: "P1", label: "Lot P1" },
    { project_id: "P2", label: "Lot P2" },
  ],
  context_claims: [],
  allocations: [],
  context_assessment: null,
  mode: "LIVE" as const,
  banner_fr: "Simulation locale de rôles",
};
const company: CompanyCaseView = {
  ...shared,
  audience: "COMPANY",
  open_questions: [],
  inbox: [],
  responses: [],
};
const officer: OfficerCaseView = {
  ...shared,
  audience: "OFFICER",
  score: {
    review_index: 40,
    raw_review_index: 40,
    cause_progress: [],
    decisive_transaction_id: "TX-001",
    evidence_coverage: "75.00",
    clarification_status: "NOT_REQUESTED",
    scope_note: "Documentaire",
    rules_version: "4",
    coverage_complete: false,
  },
  findings: [
    {
      finding_id: "F1",
      family: "QUANTITY",
      status: "UNRESOLVED",
      reason_code: "GAP",
      quantity_difference: "1000",
      unit: "unités",
      calculation_version: "4",
      evidence_refs: [],
      missing_evidence_types: [],
    },
  ],
  hypotheses: [],
  scenarios: [],
  requests: [],
  responses: [],
  proposals: [],
  candidate_passages: [],
  reference_note: null,
  mode_by_node: { checks: "LIVE", retrieval: "NOT_RUN" },
  invoice_observations: [],
  invoice_comparisons: [],
  investigator_brief: null,
  triage: {
    triage_priority: 50,
    review_index: 40,
    reason_codes: ["REVIEW_FINDING_PRESENT", "CLARIFICATION_PENDING"],
    components: { REVIEW_INDEX_BASE: 40, CLARIFICATION_PENDING: 10 },
    formula_version: "triage-demo-1",
    note_fr: "Urgence de traitement",
    not_fraud_probability: true,
  },
  clarification_deadlines: [],
  history_signals: [],
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
  enterprise_profile: null,
  monthly_activity: [],
  payment_timeline: [],
  financial_snapshot: null,
  quantity_references: [],
};

function mockApi(
  officerView: OfficerCaseView = officer,
  companyView: CompanyCaseView = company,
  historyView?: Record<string, unknown>,
  notificationsView?: Record<string, unknown>,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const role = (init?.headers as Record<string, string>)?.[
        "X-Boussla-Demo-Role"
      ];
      const payload = path.includes("/admin/enterprises")
        ? {
            items: [
              {
                company_id: "SYN-OP-001",
                display_name: "SYNTHÉTIQUE — Atelier Horizon",
                sector: "Fabrication",
                synthetic_identifier: "SYNTHETIC-MF-OP-001",
                case_id: "SYN-OP-001-CASE",
                case_version: 1,
                transaction_count: 12,
                data_kind: "SYNTHETIC",
              },
            ],
            notice_fr:
              "Administration de données synthétiques — démonstration locale.",
          }
        : path.includes("/bootstrap")
          ? {
              role: role === "OPERATOR" ? "DEMO_OPERATOR" : role,
              case_ids: role === "OPERATOR" ? [] : [shared.case_id],
              banner_fr: shared.banner_fr,
              demo_admin: Object.fromEntries(
                [
                  "can_list",
                  "can_seed",
                  "can_reset",
                  "can_add",
                  "can_delete",
                ].map((k) => [k, role === "OPERATOR"]),
              ),
            }
          : path.includes("/investigate")
            ? {
                case_id: shared.case_id,
                case_version: 1,
                question: "Pourquoi ?",
                answer_fr: "Cause documentée +40.",
                citations: [
                  {
                    source_id: "CAUSE-1",
                    kind: "CAUSE",
                    label_fr: "Cause quantité",
                    source_url: null,
                  },
                ],
                calculated_at: "2026-09-27T00:00:00Z",
                rule_version: "investigation-answer-1",
                mode: "TEMPLATE",
                authoritative: false,
                limitations: ["Revue humaine requise."],
              }
            : path.includes("/network")
              ? {
                  scope: "ALL",
                  scope_id: null,
                  nodes: [],
                  edges: [],
                  signals: [],
                  calculated_at: "2026-09-27T00:00:00Z",
                  rule_version: "case-network-2",
                  note_fr: "Relations observées.",
                }
              : path.includes("/audit")
                ? {
                    case_id: shared.case_id,
                    records: [],
                    legacy_events_without_audit: 0,
                  }
                : path.includes("/notifications")
                  ? (notificationsView ?? {
                      case_id: shared.case_id,
                      audience: role,
                      items: [],
                    })
                  : path.includes("/history") && historyView
                    ? historyView
                    : path.includes("/officer/queue")
                      ? {
                          items: [
                            {
                              case_id: shared.case_id,
                              company_display_name: shared.company_display_name,
                              case_version: 1,
                              review_index: 40,
                              evidence_coverage: "75.00",
                              active_finding_count: 1,
                              clarification_status: "NOT_REQUESTED",
                              scope_note: "Documentaire",
                              company_id: "DEMO-BAT",
                              coverage_complete: false,
                              triage_priority: 50,
                              triage_reason_codes: [
                                "REVIEW_FINDING_PRESENT",
                                "CLARIFICATION_PENDING",
                              ],
                              sector: "Construction",
                              synthetic_identifier: "DEMO-MF",
                              last_activity_at: "2026-09-07",
                              history_signal_codes: [],
                              history_anomaly: null,
                            },
                          ],
                          next_cursor: null,
                          mode: "LIVE",
                        }
                      : role === "COMPANY"
                        ? companyView
                        : officerView;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function mount({ splash = false } = {}) {
  if (splash) sessionStorage.removeItem("boussla.boot.v1");
  else sessionStorage.setItem("boussla.boot.v1", "1");
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("distinguishes a linked document from an allocation proposal after submission", async () => {
  const fetchMock = mockApi(officer, {
    ...company,
    documents: [
      {
        document: {
          document_id: "DOC-TEST",
          original_filename: "allocation.pdf",
          sha256: "test",
          page_count: 1,
          acquisition_channel: "COMPANY_UPLOAD",
          received_at: "2026-09-28T10:00:00Z",
          extraction_status: "NOT_RUN",
          processing_limitations: [],
        },
        routing: null,
        extraction: null,
        integrity: null,
        mode: "LIVE",
      },
    ],
    inbox: [
      {
        request: {
          request_id: "REQ-TEST",
          status: "PUBLISHED_IN_DEMO",
          published_at: "2026-09-28T10:00:00Z",
          allowed_document_types: [],
        },
        questions: [
          {
            question_id: "Q-TEST",
            text_fr: "Comment répartissez-vous cet achat ?",
            answer_kind: "TEXT",
            choices: [],
          },
        ],
        text_fr: "Précisez la répartition.",
        mode: "LIVE",
      },
    ],
  });
  mount();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Actions requises" }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: "Répondre à la demande" }),
  );
  fireEvent.change(
    screen.getByRole("textbox", {
      name: "Comment répartissez-vous cet achat ?",
    }),
    { target: { value: "1 000 unités pour chaque projet." } },
  );
  fireEvent.change(screen.getByLabelText("Pièce justificative existante"), {
    target: { value: "DOC-TEST" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Transmettre la réponse" }),
  );
  expect(
    await screen.findByText(
      "Réponse et pièce transmises. Aucune proposition de répartition créée.",
    ),
  ).toBeInTheDocument();
  const submitted = fetchMock.mock.calls.find(([input]) =>
    String(input).includes("/responses/REQ-TEST"),
  );
  const body = JSON.parse(String(submitted?.[1]?.body));
  expect(body.response.document_ids).toEqual(["DOC-TEST"]);
  expect(body.response).not.toHaveProperty("allocation");
});

it("switches scoped views and never shows officer priority to the company", async () => {
  mockApi();
  mount();
  expect(
    await screen.findByText("Portefeuille des entreprises", { selector: "h1" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Ouvrir Bâtiments Démo" }),
  );
  expect(
    await screen.findByText("40", { selector: ".priority-ring strong" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    await screen.findByText("40", { selector: ".priority-ring strong" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  expect(
    await screen.findByText("Votre dossier, en un regard"),
  ).toBeInTheDocument();
  expect(screen.queryByText("Priorité de revue")).not.toBeInTheDocument();
  expect(screen.queryByText("Constats")).not.toBeInTheDocument();
});

it("shows backend-provided cause contributions and separates the five indicators", async () => {
  const view: OfficerCaseView = {
    ...officer,
    score: {
      ...officer.score!,
      review_index: 20,
      raw_review_index: 40,
      cause_progress: [
        {
          transaction_id: "TX-001",
          family: "QUANTITY",
          raw_contribution: "40",
          current_contribution: "20",
          stage: "EVIDENCE_RECEIVED",
          provisional: true,
          reason_code: "PROJECT_ALLOCATION_EXCEEDS_REFERENCE",
          source_ids: ["RESP-1", "DOC-1"],
        },
      ],
    },
  };
  mockApi(view);
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Ouvrir Bâtiments Démo" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(await screen.findByText("Contributions au score")).toBeInTheDocument();
  expect(screen.getByText("40 → 20")).toBeInTheDocument();
  expect(screen.getByText("Réduction provisoire")).toBeInTheDocument();
  expect(
    screen.getByText("PROJECT_ALLOCATION_EXCEEDS_REFERENCE"),
  ).toBeInTheDocument();
  expect(screen.getByText("Signal historique")).toBeInTheDocument();
  expect(screen.getByText("Confiance opérationnelle")).toBeInTheDocument();
  expect(screen.getAllByText("Données insuffisantes")).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(screen.queryByText("Contributions au score")).not.toBeInTheDocument();
  expect(
    screen.queryByText("Confiance opérationnelle"),
  ).not.toBeInTheDocument();
});

it("shows attributed history and confidence factors only to the officer", async () => {
  mockApi({
    ...officer,
    history_signal_index: 25,
    history_signal_status: "AVAILABLE",
    history_signal_method: "HISTORY_CONTEXT_V1",
    history_signal_factors: [
      {
        reason_code: "REPEATED_INVOICE_CONFLICT",
        contribution: 25,
        source_signal_ids: ["SIG-1"],
        explanation_fr: "Conflit répété de factures",
      },
    ],
    operational_confidence_index: 0,
    operational_confidence_status: "AVAILABLE",
    operational_confidence_eligible_observations: 3,
    operational_confidence_factors: [
      {
        code: "EVIDENCE_CORROBORATION",
        numerator: 0,
        denominator: 3,
        nominal_weight: 25,
        effective_weight: "100",
        weighted_contribution: "0",
        reason_codes: ["REJECTED_PROOF"],
        source_ids: ["PROP-1"],
        explanation_fr: "Pièce rejetée par l’agent",
      },
    ],
    monthly_activity: [
      {
        month: "2025-02",
        transaction_count: 0,
        invoice_observation_count: 0,
        settled_outflow_millimes: 0,
        source_label: "Source COV-FEB",
        coverage_status: "COVERED",
        coverage_source_id: "COV-FEB",
      },
      {
        month: "2025-03",
        transaction_count: 0,
        invoice_observation_count: 0,
        settled_outflow_millimes: 0,
        source_label: "Couverture non attestée",
        coverage_status: "UNKNOWN",
        coverage_source_id: null,
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Ouvrir Bâtiments Démo" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    await screen.findByText("Conflit répété de factures"),
  ).toBeInTheDocument();
  expect(screen.getByText("Pièce rejetée par l’agent")).toBeInTheDocument();
  expect(screen.getByText("SIG-1")).toBeInTheDocument();
  expect(screen.getByText("PROP-1")).toBeInTheDocument();
  expect(screen.getByText("0/3 pièces corroborées")).toBeInTheDocument();
  expect(screen.getByText("Période couverte")).toBeInTheDocument();
  expect(screen.getByText("Couverture inconnue")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(
    screen.queryByText("Conflit répété de factures"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("Pièce rejetée par l’agent"),
  ).not.toBeInTheDocument();
});

it("shows factor-level confidence deltas in officer history", async () => {
  mockApi(officer, company, {
    revisions: [
      {
        version: 2,
        parent_version: 1,
        reason: "Demande publiée",
        created_at: "2026-09-27T00:00:00Z",
      },
    ],
    events: [],
    operational_confidence_changes: [
      {
        from_version: 2,
        to_version: 2,
        as_of: "2026-09-29T00:00:00Z",
        before_index: null,
        after_index: 0,
        factor_deltas: [
          {
            code: "TIMELINESS",
            before_contribution: null,
            after_contribution: "0",
            before_numerator: null,
            before_denominator: null,
            after_numerator: 0,
            after_denominator: 3,
            source_ids: ["REQ-1", "REQ-2", "REQ-3"],
            reason_codes: ["UNANSWERED_REQUEST"],
          },
        ],
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Ouvrir Bâtiments Démo" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Avancé" }));
  fireEvent.click(
    screen.getByText("Timeline du dossier", { selector: "summary" }),
  );
  expect(
    await screen.findByText("Confiance : données insuffisantes → 0"),
  ).toBeInTheDocument();
  expect(screen.getByText("REQ-1, REQ-2, REQ-3")).toBeInTheDocument();
});

it("shows an empty reference state and only officer-side synthesis", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Avancé" }));
  fireEvent.click(screen.getByText("Références", { selector: "summary" }));
  expect(
    await screen.findByText("Aucun passage candidat retourné"),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(screen.queryByText("Références")).not.toBeInTheDocument();
});

it("shows officer citations and disables acceptance without a source document", async () => {
  const view: OfficerCaseView = {
    ...officer,
    candidate_passages: [
      {
        rule_id: "TN-REF-1",
        document_title: "Référence publique",
        text: "Passage candidat.",
        source_url: "https://www.finances.gov.tn/",
        page: 1,
        article: null,
        mode: "TEMPLATE",
      },
    ],
    reference_note: {
      summary_fr: "Synthèse citée.",
      candidate_rule_ids: ["TN-REF-1"],
      applicability_questions: ["Quelle période ?"],
      limitations: [],
      provider_model: null,
      generation_mode: "LIVE",
      disclaimer_fr: "Synthèse indicative.",
    },
    proposals: [
      {
        proposal_id: "PROP-1",
        status: "AWAITING_HUMAN_REVIEW",
        source_document_id: null,
        transaction_id: "TX-001",
        line_id: "L1",
        unit: "pièce",
        changes: [],
      },
    ],
  };
  mockApi(view);
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Avancé" }));
  fireEvent.click(screen.getByText("Références", { selector: "summary" }));
  expect(await screen.findByText("Synthèse citée.")).toBeInTheDocument();
  expect(screen.getByText("Passage candidat.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    screen.getByRole("button", { name: "Accepter dans ce dossier" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(screen.queryByText("Synthèse citée.")).not.toBeInTheDocument();
});

it("only enables acceptance when the linked document backs the quantity cause", async () => {
  const view: OfficerCaseView = {
    ...officer,
    score: {
      ...officer.score!,
      review_index: 30,
      cause_progress: [
        {
          transaction_id: "TX-001",
          family: "QUANTITY",
          raw_contribution: "40",
          current_contribution: "30",
          stage: "EXPLANATION_RECEIVED",
          provisional: true,
          reason_code: null,
          source_ids: ["RESP-1"],
          evidence_ids: [],
        },
      ],
    },
    proposals: [
      {
        proposal_id: "PROP-1",
        status: "AWAITING_HUMAN_REVIEW",
        source_document_id: "DOC-PAY-001",
        transaction_id: "TX-001",
        line_id: "L1",
        unit: "pièce",
        changes: [],
      },
    ],
  };
  mockApi(view);
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  fireEvent.change(screen.getByLabelText("Motif de la décision sur la pièce"), {
    target: { value: "Validation documentée par l’agent" },
  });
  expect(
    screen.getByRole("button", { name: "Accepter dans ce dossier" }),
  ).toBeDisabled();
  expect(screen.getByRole("button", { name: "Rejeter" })).toBeEnabled();
  expect(
    screen.getByText(/La pièce liée ne justifie pas encore/),
  ).toBeInTheDocument();
});

it("enables acceptance when the linked document backs the quantity cause", async () => {
  const view: OfficerCaseView = {
    ...officer,
    score: {
      ...officer.score!,
      review_index: 20,
      cause_progress: [
        {
          transaction_id: "TX-001",
          family: "QUANTITY",
          raw_contribution: "40",
          current_contribution: "20",
          stage: "EVIDENCE_RECEIVED",
          provisional: true,
          reason_code: null,
          source_ids: ["RESP-1", "DOC-ALLOCATION-001"],
          evidence_ids: ["DOC-ALLOCATION-001"],
        },
      ],
    },
    proposals: [
      {
        proposal_id: "PROP-1",
        status: "AWAITING_HUMAN_REVIEW",
        source_document_id: "DOC-ALLOCATION-001",
        transaction_id: "TX-001",
        line_id: "L1",
        unit: "pièce",
        changes: [],
      },
    ],
  };
  mockApi(view);
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  fireEvent.change(screen.getByLabelText("Motif de la décision sur la pièce"), {
    target: { value: "Validation documentée par l’agent" },
  });
  expect(
    screen.getByRole("button", { name: "Accepter dans ce dossier" }),
  ).toBeEnabled();
});

it("refetches after a stale revision without retrying the write", async () => {
  const fetchMock = mockApi();
  fetchMock.mockImplementation(async (input, init) => {
    if (String(input).endsWith("/context") && init?.method === "POST")
      return new Response(
        JSON.stringify({
          error: { code: "STALE_REVISION", message: "Stale", details: {} },
        }),
        { status: 409 },
      );
    const role = (init?.headers as Record<string, string>)?.[
      "X-Boussla-Demo-Role"
    ];
    const payload = String(input).includes("/bootstrap")
      ? { role, case_ids: [shared.case_id] }
      : String(input).includes("/officer/queue")
        ? { items: [], mode: "LIVE" }
        : String(input).includes("/notifications")
          ? { case_id: shared.case_id, audience: role, items: [] }
          : role === "COMPANY"
            ? company
            : officer;
    return new Response(JSON.stringify(payload), { status: 200 });
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  fireEvent.click(screen.getByRole("button", { name: "Messages" }));
  fireEvent.click(
    await screen.findByText("Contexte déclaré", { selector: "summary" }),
  );
  fireEvent.change(
    screen.getByPlaceholderText("Décrivez l’affectation prévue…"),
    { target: { value: "Usage prévu" } },
  );
  fireEvent.change(screen.getByPlaceholderText("Ex. projet P1"), {
    target: { value: "Projet" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Enregistrer la déclaration" }),
  );
  expect(
    await screen.findByText(
      "Le dossier a changé. Les données ont été actualisées.",
    ),
  ).toBeInTheDocument();
  await waitFor(() =>
    expect(
      fetchMock.mock.calls.filter(
        ([input, init]) =>
          String(input).endsWith("/context") && init?.method === "POST",
      ),
    ).toHaveLength(1),
  );
});

const mismatch = {
  claim_id: "CLAIM-2",
  declared_horizon: "SHORT_HORIZON" as const,
  interpreted_horizon: "LONGER_HORIZON" as const,
  calculated_horizon: "LONGER_HORIZON" as const,
  declared_purpose_category: "CONSTRUCTION_PROJECT",
  interpreted_purpose_category: "CONSTRUCTION_PROJECT",
  duration_days: 546,
  consistency_status: "NEEDS_CLARIFICATION" as const,
  reason_codes: [
    "DECLARED_HORIZON_DATE_CONFLICT",
    "LONG_HORIZON_STAGE_MISSING",
  ],
  recommended_question_ids: ["Q-HORIZON-CONFIRM", "Q-PROJECT-STAGE"],
  supporting_spans: ["environ dix-huit mois"],
  corroboration_status: "NOT_ASSESSED" as const,
  interpretation_mode: "LIVE" as const,
  horizon_convention_fr: "Convention de démonstration BOUSSLA.",
};

function postBodies(fetchMock: ReturnType<typeof mockApi>, fragment: string) {
  return fetchMock.mock.calls
    .filter(
      ([input, init]) =>
        String(input).includes(fragment) && init?.method === "POST",
    )
    .map(([, init]) => JSON.parse(String(init?.body)));
}

it("renders declared / interpreted / calculated context with neutral labels", async () => {
  const fetchMock = mockApi(officer, {
    ...company,
    context_assessment: mismatch,
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Messages" }));
  fireEvent.click(
    await screen.findByText("Contexte déclaré", { selector: "summary" }),
  );
  expect(await screen.findByText("Horizon court")).toBeInTheDocument();
  expect(screen.getByText("546 jours · Horizon plus long")).toBeInTheDocument();
  expect(screen.getByText("Clarification nécessaire")).toBeInTheDocument();
  expect(
    screen.getByText(/La période déclarée diffère de celle calculée/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/n’affecte pas automatiquement la priorité/),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("DECLARED_HORIZON_DATE_CONFLICT"),
  ).not.toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(/risque|fraude|risk|fraud/i);
  const select = screen.getByLabelText(
    /Horizon du projet/,
  ) as HTMLSelectElement;
  expect([...select.options].map((o) => o.value)).toEqual([
    "",
    "SHORT_HORIZON",
    "LONGER_HORIZON",
  ]);
  fireEvent.change(select, { target: { value: "SHORT_HORIZON" } });
  fireEvent.change(screen.getByLabelText(/Usage prévu/), {
    target: { value: "Dépôt" },
  });
  fireEvent.change(screen.getByLabelText(/Bénéficiaire/), {
    target: { value: "P1" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: /Enregistrer la déclaration/ }),
  );
  await waitFor(() =>
    expect(postBodies(fetchMock, "/context")).toHaveLength(1),
  );
  expect(postBodies(fetchMock, "/context")[0].context.declared_horizon).toBe(
    "SHORT_HORIZON",
  );
});

it("answers a CHOICE question with the backend enum, not the display label", async () => {
  const inbox = [
    {
      request: {
        request_id: "REQ-1",
        status: "PUBLISHED_IN_DEMO",
        published_at: null,
        allowed_document_types: [],
      },
      questions: [
        {
          question_id: "Q-HORIZON-CONFIRM",
          text_fr: "Pouvez-vous confirmer la période prévue ?",
          answer_kind: "CHOICE",
          choices: ["SHORT_HORIZON", "LONGER_HORIZON"],
        },
      ],
      text_fr: "Demande",
      mode: "TEMPLATE" as const,
    },
  ];
  const fetchMock = mockApi(officer, { ...company, inbox });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Actions requises" }),
  );
  fireEvent.click(
    await screen.findByRole("button", { name: /Répondre à la demande/ }),
  );
  const select = (await screen.findByLabelText(
    /confirmer la période/,
  )) as HTMLSelectElement;
  expect([...select.options].map((o) => o.textContent)).toContain(
    "Projet à horizon plus long",
  );
  fireEvent.change(select, { target: { value: "LONGER_HORIZON" } });
  fireEvent.click(
    screen.getByRole("button", { name: /Transmettre la réponse/ }),
  );
  await waitFor(() =>
    expect(postBodies(fetchMock, "/responses/")).toHaveLength(1),
  );
  expect(postBodies(fetchMock, "/responses/")[0].response.answers).toEqual({
    "Q-HORIZON-CONFIRM": "LONGER_HORIZON",
  });
});

it("leaves no officer reference note or passages visible after switching to the company", async () => {
  mockApi({
    ...officer,
    candidate_passages: [
      {
        rule_id: "TN-REF-1",
        document_title: "Référence publique",
        text: "Passage officiel.",
        source_url: "https://www.finances.gov.tn/fr/node/952",
        page: null,
        article: null,
        mode: "LIVE",
      },
    ],
    reference_note: {
      summary_fr: "Synthèse réservée à l’agent.",
      candidate_rule_ids: ["TN-REF-1"],
      applicability_questions: [],
      limitations: [],
      provider_model: "gpt-test",
      generation_mode: "LIVE",
      disclaimer_fr: "Synthèse indicative.",
    },
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Avancé" }));
  fireEvent.click(screen.getByText("Références", { selector: "summary" }));
  expect(
    await screen.findByText("Synthèse réservée à l’agent."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(
    screen.queryByText("Synthèse réservée à l’agent."),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Passage officiel.")).not.toBeInTheDocument();
});

it("shows a bounded automatic request in the company inbox without an officer draft", async () => {
  mockApi(officer, {
    ...company,
    inbox: [
      {
        request: {
          request_id: "REQ-AUTO-1",
          status: "PUBLISHED_IN_DEMO",
          published_at: "2026-09-26T10:00:00Z",
          allowed_document_types: ["PAYMENT_RECORD"],
          origin: "AUTOMATIC",
          reason_text_fr: "Règlement à préciser.",
          target_response_at: "2026-10-03T10:00:00Z",
          target_kind: "DEMO_SERVICE_TARGET",
          overdue_state: "FOLLOW_UP_DUE",
        },
        questions: [
          {
            question_id: "Q-PAY",
            text_fr: "Quelle pièce documente le règlement ?",
            answer_kind: "TEXT",
            choices: [],
          },
        ],
        text_fr: "Merci de préciser le règlement observé.",
        mode: "LIVE",
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  expect(await screen.findByText("Justification requise")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Voir la demande" }));
  expect(
    await screen.findByText("Demande automatique BOUSSLA"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Précisions demandées automatiquement à partir des informations disponibles.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Cible de réponse de démonstration/),
  ).toBeInTheDocument();
  expect(screen.getByText("Relance à prévoir")).toBeInTheDocument();
  expect(document.body.textContent).not.toMatch(
    /fraude détectée|suspicious|délai légal dépassé/i,
  );
  expect(
    screen.getByText("Quelle pièce documente le règlement ?"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /Répondre à la demande/ }),
  ).toBeEnabled();
  expect(document.body.textContent).not.toMatch(
    /probabilit[ée] de fraude|fraud probability/i,
  );
});

it("only offers general company use when the server capability permits a null project", async () => {
  const fetchMock = mockApi(officer, {
    ...company,
    capabilities: { supports_null_project_id: true },
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  fireEvent.click(await screen.findByRole("button", { name: "Messages" }));
  fireEvent.click(
    await screen.findByText("Contexte déclaré", { selector: "summary" }),
  );
  expect(
    await screen.findByRole("option", {
      name: "Aucun projet / usage général de l’entreprise",
    }),
  ).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Projet concerné"), {
    target: { value: "__GENERAL__" },
  });
  fireEvent.change(
    screen.getByPlaceholderText("Décrivez l’affectation prévue…"),
    {
      target: { value: "Usage général déclaré" },
    },
  );
  fireEvent.change(screen.getByPlaceholderText("Ex. projet P1"), {
    target: { value: "Entreprise" },
  });
  fireEvent.click(
    screen.getByRole("button", { name: "Enregistrer la déclaration" }),
  );
  await waitFor(() =>
    expect(postBodies(fetchMock, "/context")).toHaveLength(1),
  );
  expect(postBodies(fetchMock, "/context")[0].context.project_id).toBeNull();
});

it("shows triage separately from the review index in the officer dossier", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  expect(
    screen.getByText("50", { selector: ".portfolio-triage" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("40", { selector: ".portfolio-index" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    await screen.findByText("Urgence de traitement (triage)"),
  ).toBeInTheDocument();
  expect(
    screen.getAllByText("Clarification en attente").length,
  ).toBeGreaterThan(0);
  expect(document.body.textContent).not.toMatch(/probabilit[ée] de fraude/i);
});

it("keeps demo administration behind the operator role", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  expect(
    screen.queryByRole("button", { name: "Données démo" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Opérateur démo" }));
  expect(
    await screen.findByText(
      "Administration de données synthétiques — démonstration locale.",
    ),
  ).toBeInTheDocument();
  expect(
    await screen.findByText("SYNTHÉTIQUE — Atelier Horizon"),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Supprimer" })).toBeEnabled();
});

it("renders the brand mark and a time-bounded boot splash once per session", async () => {
  mockApi();
  mount({ splash: true });
  expect(
    screen.getByRole("status", { name: "Chargement de BOUSSLA" }),
  ).toBeInTheDocument();
  expect(
    screen.getAllByRole("img", { name: "BOUSSLA" }).length,
  ).toBeGreaterThan(0);
  expect(sessionStorage.getItem("boussla.boot.v1")).toBe("1");
  await waitFor(
    () =>
      expect(
        screen.queryByRole("status", { name: "Chargement de BOUSSLA" }),
      ).not.toBeInTheDocument(),
    { timeout: 1600 },
  );
  expect(
    screen.getByText("Portefeuille des entreprises", { selector: "h1" }),
  ).toBeInTheDocument();
});

it("renders backend indicator explanations without inventing missing values", async () => {
  mockApi({
    ...officer,
    indicators: {
      operational_confidence: {
        value: null,
        status: "INSUFFICIENT_DATA",
        factors: [],
        explanation: "Échantillon trop faible pour une estimation.",
        calculated_at: "2026-09-27T00:00:00Z",
        rule_version: "confidence-test-rule",
        sample_size: 2,
      },
      document_review: {
        value: "37",
        status: "PROVISIONAL",
        factors: [],
        explanation: "Valeur calculée par le serveur.",
        calculated_at: "2026-09-27T00:00:00Z",
        rule_version: "review-test-rule",
        sample_size: 1,
      },
    },
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Ouvrir Bâtiments Démo" }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  fireEvent.click(await screen.findByText("Comprendre les cinq indicateurs"));
  expect(screen.getByText("Indice de revue : 37")).toBeInTheDocument();
  expect(
    screen.getByText("Confiance opérationnelle : Données insuffisantes"),
  ).toBeInTheDocument();
  expect(screen.getByText(/confidence-test-rule/)).toBeInTheDocument();
});

it("keeps five primary officer spaces and four company spaces role scoped", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Agent$/ }));
  for (const name of [
    "Dashboard",
    "Dossiers",
    "Réseau",
    "Historique",
    "Notifications",
    "Avancé",
  ])
    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Réseau" }));
  expect(
    await screen.findByText("Réseau", { selector: "h1" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
  expect(
    await screen.findByText("Notifications", { selector: "h1" }),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  for (const name of [
    "Mes dossiers",
    "Actions requises",
    "Documents",
    "Messages",
  ])
    expect(screen.getByRole("button", { name })).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Réseau" }),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Priorité de revue")).not.toBeInTheDocument();
});

it("orders the dossier around review, proof and a human decision", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  const navigation = screen.getByRole("navigation", {
    name: "Sections du dossier",
  });
  expect(
    Array.from(navigation.querySelectorAll("a"), (link) => link.textContent),
  ).toEqual([
    "Synthèse",
    "Pourquoi ?",
    "Preuves",
    "Actions",
    "Timeline",
    "Décision",
  ]);
  expect(screen.getByText("Contributions au score")).toBeInTheDocument();
  expect(screen.getByText(/pièces disponibles/)).toBeInTheDocument();
  expect(screen.getByText("Actions recommandées")).toBeInTheDocument();
  expect(await screen.findByText("Chronologie")).toBeInTheDocument();
  expect(screen.getByText("Décision de l’agent")).toBeInTheDocument();
  expect(screen.getByText("Analyses complémentaires")).toBeInTheDocument();
});

it("links an undeclared company context to its message form", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Déclarer le contexte" }),
  );
  expect(
    await screen.findByText("Messages et contexte", { selector: "h1" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("Justification requise")).not.toBeInTheDocument();
});

it("tells the recorded cause and event story without inventing a score transition", async () => {
  const baseCause = {
    cause_id: "CAUSE-1",
    transaction_id: "TX-1",
    family: "QUANTITY",
    raw_contribution: "40",
    current_contribution: "40",
    stage: "UNRESOLVED",
    provisional: false,
    reason_code: "GAP",
    source_ids: ["INV-1"],
  };
  mockApi(officer, company, {
    revisions: [
      {
        version: 1,
        parent_version: null,
        reason: "Facture reçue",
        created_at: "2026-09-27T10:32:00Z",
        score_snapshot: {
          ...officer.score,
          review_index: 40,
          cause_progress: [baseCause],
        },
      },
      {
        version: 2,
        parent_version: 1,
        reason: "Réponse entreprise reçue",
        created_at: "2026-09-27T13:02:00Z",
        score_snapshot: {
          ...officer.score,
          review_index: 30,
          cause_progress: [
            {
              ...baseCause,
              current_contribution: "30",
              stage: "EXPLANATION_RECEIVED",
              provisional: true,
            },
          ],
        },
      },
      {
        version: 3,
        parent_version: 2,
        reason: "Demande publiée",
        created_at: "2026-09-27T13:08:00Z",
        score_snapshot: null,
      },
    ],
    events: [
      {
        event_id: "EV-2",
        kind: "RESPONSE",
        summary: "Réponse reçue",
        case_version: 2,
        at: "2026-09-27T13:02:00Z",
        actor_id: "company-demo",
        fact_ids: ["RESP-1"],
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    await screen.findByText("Indice de revue : 40 → 30"),
  ).toBeInTheDocument();
  expect(screen.getByText(/40 → 30 · provisoire/)).toBeInTheDocument();
  expect(screen.getByText("Réponse reçue")).toBeInTheDocument();
  expect(screen.getByText(/RESP-1/)).toBeInTheDocument();
  expect(screen.getAllByText(/Indice de revue :/)).toHaveLength(1);
});

it("shows the no-write resolution impact only to the officer", async () => {
  mockApi({
    ...officer,
    impact_if_resolved: [
      {
        step: 1,
        cause_id: "CAUSE-1",
        family: "QUANTITY",
        transaction_id: "TX-1",
        before_index: 40,
        after_index: 0,
        source_ids: ["INV-1"],
        case_version: 1,
        calculated_at: "2026-09-27T10:00:00Z",
        rule_version: "resolution-impact-1",
        hypothetical: true,
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(await screen.findByText("Impact si résolu")).toBeInTheDocument();
  expect(screen.getByText("40 → 0")).toBeInTheDocument();
  expect(
    screen.getByText(/Simulation — aucune modification appliquée au dossier/),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(screen.queryByText("Impact si résolu")).not.toBeInTheDocument();
});

it("compares company habit to the current period without treating uncovered months as zero", async () => {
  mockApi(
    {
      ...officer,
      behavior_profile: {
        as_of: "2026-09-27T00:00:00Z",
        observed_period: "2026-09",
        baseline_periods: ["2026-06", "2026-07", "2026-08"],
        rule_version: "self-baseline-4",
        signals: [
          {
            code: "MONTHLY_AMOUNT_DEVIATION",
            metric_code: "MONTHLY_AMOUNT",
            currency: "TND",
            observed_value: "800",
            baseline_value: "300",
            ratio: "2.67",
            data_quality: "LIMITED_DATA",
            baseline_months: 3,
            current_sample_size: 1,
            source_ids: ["INV-1"],
            explanation_fr:
              "Montant mensuel observé : 800 contre 300 (×2.67). Signal de revue descriptif.",
            rule_version: "self-baseline-4",
          },
        ],
        metrics: [
          {
            code: "INVOICE_VOLUME",
            label_fr: "Factures par mois",
            current_value: "8",
            baseline_value: "3",
            change_percent: "166.7",
            status: "AVAILABLE",
            unit: "factures",
            currency: null,
            sample_size: 3,
            source_ids: ["INV-1"],
            explanation_fr: "Moyenne de trois mois couverts.",
          },
        ],
      },
      monthly_activity: [
        {
          month: "2026-08",
          transaction_count: 0,
          invoice_observation_count: 0,
          settled_outflow_millimes: 0,
          source_label: "Couverture inconnue",
          coverage_status: "UNKNOWN",
          coverage_source_id: null,
        },
        {
          month: "2026-09",
          transaction_count: 8,
          invoice_observation_count: 8,
          settled_outflow_millimes: 0,
          source_label: "Source COV-SEP",
          coverage_status: "COVERED",
          coverage_source_id: "COV-SEP",
        },
      ],
    },
    company,
    { revisions: [], events: [] },
  );
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Historique" }));
  expect(
    await screen.findByText("Habitude vs période actuelle"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Écart : 166.7 % · 3 mois exploitables"),
  ).toBeInTheDocument();
  expect(screen.getByText("Montant mensuel inhabituel")).toBeInTheDocument();
  expect(
    screen.getByText(/Données limitées · 1 observation/),
  ).toBeInTheDocument();
  expect(screen.getByTitle("2026-08 : couverture inconnue")).toHaveTextContent(
    "—",
  );
});

it("shows sourced investigation answers only in the officer dossier", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Examiner les sources" }),
  );
  expect(await screen.findByText("Cause documentée +40.")).toBeInTheDocument();
  expect(screen.getByText(/CAUSE-1/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(
    screen.queryByText("Assistant d’investigation"),
  ).not.toBeInTheDocument();
  expect(screen.queryByText("Cause documentée +40.")).not.toBeInTheDocument();
});

it("requires a reason and resolved causes for dossier closure while allowing an escalation", async () => {
  const fetchMock = mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Dossiers" }));
  expect(
    screen.getByRole("button", { name: "Résoudre le dossier" }),
  ).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Escalader le dossier" }),
  ).toBeDisabled();
  fireEvent.change(screen.getByLabelText("Motif de la décision"), {
    target: { value: "Revue renforcée demandée par l’agent" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Escalader le dossier" }));
  await waitFor(() =>
    expect(postBodies(fetchMock, "/decisions")).toHaveLength(1),
  );
  expect(postBodies(fetchMock, "/decisions")[0]).toMatchObject({
    kind: "ESCALATE",
    expected_version: 1,
    reason: "Revue renforcée demandée par l’agent",
  });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  expect(
    screen.queryByText("Décision de revue interne"),
  ).not.toBeInTheDocument();
});

it("labels calculated agent notification signals separately from recorded events", async () => {
  mockApi(officer, company, undefined, {
    case_id: shared.case_id,
    audience: "OFFICER",
    items: [
      {
        notification_id: "CURRENT-URGENT",
        kind: "CASE_URGENT",
        title_fr: "Dossier urgent à traiter",
        message_fr: "Urgence opérationnelle 82/100.",
        occurred_at: "2026-09-27T00:00:00Z",
        case_version: 1,
        source_event_id: null,
        source_ids: ["REVIEW_FINDING_PRESENT"],
        status: "CURRENT_SIGNAL",
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
  expect(
    await screen.findByText("Dossier urgent à traiter"),
  ).toBeInTheDocument();
  expect(screen.getByText("Signal courant · à réévaluer")).toBeInTheDocument();
  expect(
    screen.getByText("Sources : REVIEW_FINDING_PRESENT"),
  ).toBeInTheDocument();
});

it("marks only recorded notifications read through the scoped API", async () => {
  const fetchMock = mockApi(officer, company, undefined, {
    case_id: shared.case_id,
    audience: "OFFICER",
    items: [
      {
        notification_id: "EV-00001",
        kind: "UPLOAD",
        title_fr: "Document reçu",
        message_fr: "Pièce reçue.",
        occurred_at: "2026-09-27T00:00:00Z",
        case_version: 1,
        source_event_id: "EV-00001",
        status: "RECORDED",
        read_at: null,
      },
      {
        notification_id: "CURRENT-URGENT",
        kind: "CASE_URGENT",
        title_fr: "Dossier urgent à traiter",
        message_fr: "Urgence à réévaluer.",
        occurred_at: "2026-09-27T00:00:00Z",
        case_version: 1,
        source_event_id: null,
        status: "CURRENT_SIGNAL",
        read_at: null,
      },
    ],
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Marquer comme lu" }),
  );
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/cases/CASE-BRICKS-001/notifications/EV-00001/read",
      expect.objectContaining({ method: "POST" }),
    ),
  );
  expect(screen.getAllByText("Signal courant · à réévaluer")).toHaveLength(1);
});
it("exposes the current section, role state, and a main-content skip link", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  const navigation = screen.getByRole("navigation", {
    name: "Navigation principale",
  });
  expect(navigation.querySelector('[aria-current="page"]')).toHaveTextContent(
    "Dashboard",
  );
  expect(
    screen.getByRole("link", { name: "Aller au contenu principal" }),
  ).toHaveAttribute("href", "#main-content");
  expect(document.getElementById("main-content")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /^Agent$/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  fireEvent.click(screen.getByRole("button", { name: /^Dossiers$/ }));
  expect(navigation.querySelector('[aria-current="page"]')).toHaveTextContent(
    "Dossiers",
  );
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  expect(screen.getByRole("button", { name: /^Entreprise$/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(navigation.querySelector('[aria-current="page"]')).toHaveTextContent(
    "Mes dossiers",
  );
});

it("bypasses the boot overlay for reduced motion", async () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: true })),
  );
  mockApi();
  mount({ splash: true });
  expect(
    screen.queryByRole("status", { name: "Chargement de BOUSSLA" }),
  ).not.toBeInTheDocument();
  expect(
    await screen.findByText("Portefeuille des entreprises", { selector: "h1" }),
  ).toBeInTheDocument();
});

it("keeps the service mode neutral rather than presenting it as a validated outcome", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  expect(document.querySelector(".topbar .badge")).toHaveTextContent("LIVE");
  expect(document.querySelector(".topbar .badge")).not.toHaveClass("good");
});
