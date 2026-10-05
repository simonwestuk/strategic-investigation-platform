/**
 * Fixture-mode API (`NEXT_PUBLIC_USE_FIXTURES=true`). Serves real responses captured from the
 * backend so the UI can be demoed, screenshotted and tested without it. Responding to a review
 * advances to the next captured snapshot, and a submitted decision is merged into the final one.
 */
import auditJson from "../../fixtures/audit.json";
import claimChainJson from "../../fixtures/claim-chain.json";
import investigationsJson from "../../fixtures/investigations.json";
import scenariosJson from "../../fixtures/scenarios.json";
import sourceJson from "../../fixtures/source.json";
import { ApiError, type ApiClient } from "./api";
import { deriveClaimChain } from "./claim-chain";
import { type FixtureStage, fixtureStageStore } from "./fixture-stage";
import { getPersona, hasRole } from "./roles";
import type {
  AuditEvent,
  ClaimChain,
  Decision,
  DecisionType,
  InvestigationDetail,
  InvestigationSummary,
  Scenario,
  SourceDetail,
} from "./types";

const loaders: Record<FixtureStage, () => Promise<unknown>> = {
  "privacy-review": () => import("../../fixtures/investigation-privacy-review.json").then((m) => m.default),
  "options-review": () => import("../../fixtures/investigation-options-review.json").then((m) => m.default),
  "awaiting-decision": () => import("../../fixtures/investigation-awaiting-decision.json").then((m) => m.default),
  decided: () => import("../../fixtures/investigation-decided.json").then((m) => m.default),
};

const NEXT_STAGE: Record<FixtureStage, FixtureStage> = {
  "privacy-review": "options-review",
  "options-review": "awaiting-decision",
  "awaiting-decision": "decided",
  decided: "decided",
};

let submittedDecision: Decision | null = null;

const clone = <T>(v: T): T => structuredClone(v);
const pause = () => new Promise((r) => setTimeout(r, 120));

async function loadDetail(): Promise<InvestigationDetail> {
  const stage = fixtureStageStore.get();
  const detail = clone((await loaders[stage]()) as InvestigationDetail);
  if (stage === "decided" && submittedDecision) detail.decision = submittedDecision;
  return detail;
}

function assertKnown(id: string): void {
  const known = (investigationsJson as unknown as InvestigationSummary[]).some((i) => i.id === id);
  if (!known) throw new ApiError(404, "Investigation not found");
}

function readOnly(what: string): never {
  throw new ApiError(501, `${what} is not available in fixture mode. Run against the live API to try it.`);
}

export const fixtureApi: ApiClient = {
  async me() {
    const p = getPersona();
    return { kind: "human", id: `dev:${p.userId}`, display_name: p.displayName, roles: p.roles };
  },
  async scenarios() {
    return clone(scenariosJson as unknown as Scenario[]);
  },
  async listInvestigations() {
    const detail = await loadDetail();
    return (investigationsJson as unknown as InvestigationSummary[]).map((s) =>
      s.id === detail.summary.id ? detail.summary : s,
    );
  },
  async createInvestigation() {
    return readOnly("Creating investigations");
  },
  async getInvestigation(id) {
    assertKnown(id);
    await pause();
    return loadDetail();
  },
  async startInvestigation() {
    return readOnly("Starting investigations");
  },
  async uploadDocument() {
    return readOnly("Uploading documents");
  },
  async getDocument(id, documentId) {
    assertKnown(id);
    const detail = await loadDetail();
    const doc = detail.intake.find((d) => d.id === documentId);
    if (!doc) throw new ApiError(404, "Document not found");
    return { id: doc.id, title: doc.title, status: doc.status, scan: doc.scan, sanitised_text: doc.sanitised_preview };
  },
  async getClaimChain(id, claimId) {
    assertKnown(id);
    await pause();
    const captured = claimChainJson as unknown as ClaimChain;
    if (captured.claim.id === claimId) return clone(captured);
    const chain = deriveClaimChain(await loadDetail(), claimId);
    if (!chain) throw new ApiError(404, "Claim not found");
    return chain;
  },
  async getSource(id, sourceId) {
    assertKnown(id);
    const captured = sourceJson as unknown as SourceDetail;
    const detail = await loadDetail();
    const source = sourceId === captured.id ? captured : detail.sources.find((s) => s.id === sourceId);
    if (!source) throw new ApiError(404, "Source not found");
    // Fixture approximation of the stored sanitised content: the intake preview, when there is one.
    const intake = detail.intake.find((d) => d.id === source.privacy_document_id);
    return { ...clone(source), content: intake?.sanitised_preview ?? null };
  },
  async getAudit(id) {
    assertKnown(id);
    return clone(auditJson as unknown as AuditEvent[]);
  },
  async respondToReview(id, reviewId, body) {
    assertKnown(id);
    const detail = await loadDetail();
    const review = detail.reviews.find((r) => r.id === reviewId);
    if (!review) throw new ApiError(404, "Review not found");
    const persona = getPersona();
    if (!hasRole(persona.roles, review.required_role)) {
      throw new ApiError(403, `Requires role '${review.required_role}'.`);
    }
    if (!review.allowed_actions.includes(body.action)) {
      throw new ApiError(422, `Action '${body.action}' not allowed.`);
    }
    if (review.status !== "pending") throw new ApiError(409, "Review already resolved.");
    if (body.action === "request_further_investigation") {
      throw new ApiError(501, "Further research cannot be simulated in fixture mode; the request was not sent.");
    }
    if (review.kind === "decision" && body.decision) {
      submittedDecision = {
        id: "dec_fixture",
        decision_type: body.decision.decision_type as DecisionType,
        statement: body.decision.statement,
        rationale: body.decision.rationale,
        option_ids: body.decision.option_ids ?? [],
        conditions: body.decision.conditions ?? [],
        uncertainties_acknowledged: body.decision.uncertainties_acknowledged ?? false,
        acknowledged_unknown_claim_ids: body.decision.acknowledged_unknown_claim_ids ?? [],
        decided_by: { kind: "human", id: `dev:${persona.userId}`, display_name: persona.displayName, roles: persona.roles },
        decided_at: new Date().toISOString(),
        review_id: review.id,
      };
    }
    fixtureStageStore.set(NEXT_STAGE[fixtureStageStore.get()]);
    return (await loadDetail()).summary;
  },
};
