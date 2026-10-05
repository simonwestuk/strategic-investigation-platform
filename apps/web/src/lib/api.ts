/**
 * Typed API client. Every request carries the active persona's dev-auth headers; the server is the
 * authority on RBAC (403s are surfaced as `ApiError`). In fixture mode the same interface is served
 * from the bundled JSON fixtures (see `fixture-api.ts`).
 */
import { API_BASE_URL, USE_FIXTURES } from "./env";
import { getPersona, personaHeaders } from "./roles";
import type {
  Actor,
  AuditEvent,
  ClaimChain,
  CreateInvestigationBody,
  DocumentDetail,
  IntakeDocument,
  InvestigationDetail,
  InvestigationSummary,
  ReviewResponseBody,
  Scenario,
  SourceDetail,
  UploadDocumentInput,
} from "./types";

export interface ApiClient {
  me(): Promise<Actor>;
  scenarios(): Promise<Scenario[]>;
  listInvestigations(): Promise<InvestigationSummary[]>;
  createInvestigation(body: CreateInvestigationBody): Promise<InvestigationSummary>;
  getInvestigation(id: string): Promise<InvestigationDetail>;
  startInvestigation(id: string): Promise<InvestigationSummary>;
  uploadDocument(id: string, input: UploadDocumentInput): Promise<IntakeDocument>;
  getDocument(id: string, documentId: string): Promise<DocumentDetail>;
  getClaimChain(id: string, claimId: string): Promise<ClaimChain>;
  getSource(id: string, sourceId: string): Promise<SourceDetail>;
  getAudit(id: string): Promise<AuditEvent[]>;
  respondToReview(id: string, reviewId: string, body: ReviewResponseBody): Promise<InvestigationSummary>;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  get forbidden(): boolean {
    return this.status === 403;
  }
}

function detailMessage(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join("; ");
    }
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  for (const [k, v] of Object.entries(personaHeaders(getPersona()))) headers.set(k, v);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  headers.set("Accept", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, cache: "no-store" });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`);
  }
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, detailMessage(body, `${res.status} ${res.statusText}`));
  }
  return body as T;
}

const enc = encodeURIComponent;

export const liveApi: ApiClient = {
  me: () => request("/api/me"),
  scenarios: () => request("/api/scenarios"),
  listInvestigations: () => request("/api/investigations"),
  createInvestigation: (body) => request("/api/investigations", { method: "POST", body: JSON.stringify(body) }),
  getInvestigation: (id) => request(`/api/investigations/${enc(id)}`),
  startInvestigation: (id) => request(`/api/investigations/${enc(id)}/start`, { method: "POST" }),
  uploadDocument: (id, input) => {
    const form = new FormData();
    form.set("file", input.file);
    if (input.title) form.set("title", input.title);
    form.set("source_type", input.sourceType);
    form.set("confidentiality", input.confidentiality);
    return request(`/api/investigations/${enc(id)}/documents`, { method: "POST", body: form });
  },
  getDocument: (id, docId) => request(`/api/investigations/${enc(id)}/documents/${enc(docId)}`),
  getClaimChain: (id, claimId) => request(`/api/investigations/${enc(id)}/claims/${enc(claimId)}`),
  getSource: (id, sourceId) => request(`/api/investigations/${enc(id)}/sources/${enc(sourceId)}`),
  getAudit: (id) => request(`/api/investigations/${enc(id)}/audit`),
  respondToReview: (id, reviewId, body) =>
    request(`/api/investigations/${enc(id)}/reviews/${enc(reviewId)}/respond`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

let fixtureApi: Promise<ApiClient> | null = null;

function lazyFixtureApi(): Promise<ApiClient> {
  fixtureApi ??= import("./fixture-api").then((m) => m.fixtureApi);
  return fixtureApi;
}

/** Fixture-mode client is code-split and only loaded when `NEXT_PUBLIC_USE_FIXTURES=true`. */
function delegate<K extends keyof ApiClient>(key: K): ApiClient[K] {
  const fn = (...args: unknown[]) =>
    lazyFixtureApi().then((client) => (client[key] as (...a: unknown[]) => unknown)(...args));
  return fn as ApiClient[K];
}

export const api: ApiClient = USE_FIXTURES
  ? {
      me: delegate("me"),
      scenarios: delegate("scenarios"),
      listInvestigations: delegate("listInvestigations"),
      createInvestigation: delegate("createInvestigation"),
      getInvestigation: delegate("getInvestigation"),
      startInvestigation: delegate("startInvestigation"),
      uploadDocument: delegate("uploadDocument"),
      getDocument: delegate("getDocument"),
      getClaimChain: delegate("getClaimChain"),
      getSource: delegate("getSource"),
      getAudit: delegate("getAudit"),
      respondToReview: delegate("respondToReview"),
    }
  : liveApi;
