import type {
  Role,
  ApiErrorBody,
  Bootstrap,
  CompanyCaseView,
  OfficerCaseView,
  QueuePage,
  HistoryView,
  AuditView,
  NotificationFeedView,
  NetworkView,
  InvestigationAnswer,
  ClarificationDraft,
  RequestView,
  RevisionResult,
  DocumentView,
  ResponseView,
  AdminEnterprise,
  AdminResult,
} from "./types";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(
  role: Role,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch(`/api${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "X-Boussla-Demo-Role": role, ...init.headers },
    });
    if (!response.ok) {
      const payload = (await response
        .json()
        .catch(() => null)) as ApiErrorBody | null;
      throw new ApiError(
        payload?.error?.code ?? "NETWORK_ERROR",
        payload?.error?.message ?? "Le service est indisponible.",
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "NETWORK_ERROR",
      error instanceof DOMException && error.name === "AbortError"
        ? "Le service met trop de temps à répondre."
        : "Connexion au service impossible.",
    );
  } finally {
    clearTimeout(timeout);
  }
}

export const api = {
  bootstrap: (r: Role) => request<Bootstrap>(r, "/demo/bootstrap"),
  case: (r: Role, id: string) =>
    request<CompanyCaseView | OfficerCaseView>(
      r,
      `/cases/${encodeURIComponent(id)}`,
    ),
  queue: (cursor?: string) =>
    request<QueuePage>(
      "OFFICER",
      `/officer/queue${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`,
    ),
  history: (r: Role, id: string) =>
    request<HistoryView>(r, `/cases/${encodeURIComponent(id)}/history`),
  audit: (id: string) =>
    request<AuditView>("OFFICER", `/cases/${encodeURIComponent(id)}/audit`),
  notifications: (r: Role, id: string) =>
    request<NotificationFeedView>(
      r,
      `/cases/${encodeURIComponent(id)}/notifications`,
    ),
  askInvestigation: (id: string, question: string) =>
    request<InvestigationAnswer>(
      "OFFICER",
      `/cases/${encodeURIComponent(id)}/investigate`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      },
    ),
  network: () => request<NetworkView>("OFFICER", "/network"),
  networkCase: (id: string) =>
    request<NetworkView>("OFFICER", `/network/case/${encodeURIComponent(id)}`),
  networkCompany: (id: string) =>
    request<NetworkView>(
      "OFFICER",
      `/network/company/${encodeURIComponent(id)}`,
    ),
  post: <T>(
    r: Role,
    path: string,
    payload: object,
    key = crypto.randomUUID(),
  ) =>
    request<T>(r, path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify(payload),
    }),
  upload: (
    r: Role,
    id: string,
    file: File,
    expected_version: number,
    key = crypto.randomUUID(),
  ) => {
    const form = new FormData();
    form.append("file", file);
    form.append("expected_version", String(expected_version));
    return request<DocumentView>(
      r,
      `/cases/${encodeURIComponent(id)}/documents`,
      { method: "POST", headers: { "Idempotency-Key": key }, body: form },
    );
  },
  confirmTranscription: (
    id: string,
    proposal: string,
    version: number,
    fields: Record<string, string>,
  ) =>
    api.post<CompanyCaseView>(
      "COMPANY",
      `/cases/${encodeURIComponent(id)}/transcriptions/${encodeURIComponent(proposal)}/confirm`,
      {
        expected_version: version,
        fields,
      },
    ),
  context: (id: string, version: number, context: object) =>
    api.post<CompanyCaseView>("COMPANY", `/cases/${id}/context`, {
      expected_version: version,
      context,
    }),
  prepare: (id: string, version: number) =>
    api.post<ClarificationDraft>(
      "OFFICER",
      `/cases/${id}/clarifications/prepare`,
      { expected_version: version },
    ),
  publish: (id: string, draft: string, version: number) =>
    api.post<RequestView>(
      "OFFICER",
      `/cases/${id}/clarifications/${draft}/publish`,
      { expected_version: version },
    ),
  respond: (id: string, req: string, version: number, response: object) =>
    api.post<ResponseView>("COMPANY", `/cases/${id}/responses/${req}`, {
      expected_version: version,
      response,
    }),
  decide: (
    id: string,
    proposal: string,
    version: number,
    action: "accept" | "reject",
  ) =>
    api.post<RevisionResult>(
      "OFFICER",
      `/cases/${id}/proposals/${proposal}/${action}`,
      {
        expected_version: version,
        reason:
          action === "reject" ? "Pièce non retenue dans ce dossier" : undefined,
      },
    ),
  /** Synthetic demo administration: DEMO_OPERATOR role only (server-enforced). */
  admin: {
    list: () =>
      request<{ items: AdminEnterprise[]; notice_fr: string }>(
        "OPERATOR",
        "/admin/enterprises",
      ),
    seed: () => api.post<AdminResult>("OPERATOR", "/admin/portfolio/seed", {}),
    reset: () =>
      api.post<AdminResult>("OPERATOR", "/admin/portfolio/reset", {
        confirm: "RESET",
      }),
    add: (display_name: string, sector: string) =>
      api.post<AdminEnterprise>("OPERATOR", "/admin/enterprises", {
        display_name,
        sector,
      }),
    remove: (company_id: string) =>
      request<AdminResult>(
        "OPERATOR",
        `/admin/enterprises/${encodeURIComponent(company_id)}`,
        {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirm: company_id }),
        },
      ),
  },
};
