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
  quantity_references: [],
};

function mockApi(
  officerView: OfficerCaseView = officer,
  companyView: CompanyCaseView = company,
) {
  const fetchMock = vi.fn(
    async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      const role = (init?.headers as Record<string, string>)?.[
        "X-Boussla-Demo-Role"
      ];
      const payload = path.includes("/bootstrap")
        ? { role, case_ids: [shared.case_id], banner_fr: shared.banner_fr }
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

function mount() {
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
  expect(await screen.findByText("Entreprise 360")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dossier" }));
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

it("shows an empty reference state and only officer-side synthesis", async () => {
  mockApi();
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: "Références" }));
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
  fireEvent.click(screen.getByRole("button", { name: "Références" }));
  expect(await screen.findByText("Synthèse citée.")).toBeInTheDocument();
  expect(screen.getByText("Passage candidat.")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Dossier" }));
  expect(
    screen.getByRole("button", { name: "Accepter dans ce dossier" }),
  ).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  expect(screen.queryByText("Synthèse citée.")).not.toBeInTheDocument();
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
        : role === "COMPANY"
          ? company
          : officer;
    return new Response(JSON.stringify(payload), { status: 200 });
  });
  mount();
  await screen.findByText("Portefeuille des entreprises", { selector: "h1" });
  fireEvent.click(screen.getByRole("button", { name: /^Entreprise$/ }));
  await screen.findByText("Votre dossier, en un regard");
  fireEvent.click(screen.getByRole("button", { name: "Contexte" }));
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
  fireEvent.click(await screen.findByRole("button", { name: "Contexte" }));
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
  fireEvent.click(await screen.findByRole("button", { name: "Demandes" }));
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
  fireEvent.click(screen.getByRole("button", { name: "Références" }));
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
          overdue_state: "ON_TIME",
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
  fireEvent.click(await screen.findByRole("button", { name: "Demandes" }));
  expect(
    await screen.findByText("BOUSSLA a demandé automatiquement des précisions"),
  ).toBeInTheDocument();
  expect(screen.getByText(/Règlement à préciser/)).toBeInTheDocument();
  expect(
    screen.getByText(/Date cible de réponse \(démonstration\)/),
  ).toBeInTheDocument();
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
  fireEvent.click(await screen.findByRole("button", { name: "Contexte" }));
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
