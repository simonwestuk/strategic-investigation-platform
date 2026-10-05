/**
 * Domain types for the UI, derived from the generated OpenAPI types (`api-types.ts`).
 *
 * FastAPI marks every field that has a server-side default as optional in the OpenAPI schema
 * (e.g. `id?: string`), but responses always serialise those defaults. `Resp<T>` therefore makes
 * response objects deeply non-optional (nullability is preserved), so components do not have to
 * guard against `undefined` ids. Request bodies keep the raw (optional) schema types.
 */
import type { components } from "./api-types";

type Schemas = components["schemas"];

export type Resp<T> = T extends readonly (infer U)[]
  ? Resp<U>[]
  : T extends object
    ? { [K in keyof T]-?: Resp<T[K]> }
    : T;

// ---- enums ----------------------------------------------------------------------------------
export type Classification = Schemas["Classification"];
export type ConfidenceBand = Schemas["ConfidenceBand"];
export type HypothesisStatus = Schemas["HypothesisStatus"];
export type HypothesisOrigin = Schemas["HypothesisOrigin"];
export type Role = Schemas["Role"];
export type ReviewKind = Schemas["ReviewKind"];
export type ReviewAction = Schemas["ReviewAction"];
export type DecisionType = Schemas["DecisionType"];
export type AuthorityTier = Schemas["AuthorityTier"];
export type Freshness = Schemas["Freshness"];
export type QuoteVerification = Schemas["QuoteVerification"];
export type EvidenceKind = Schemas["EvidenceKind"];
export type TaskStatus = Schemas["TaskStatus"];
export type TaskOrigin = Schemas["TaskOrigin"];
export type ResearchMethod = Schemas["ResearchMethod"];
export type Level = Schemas["Level"];
export type Severity = Schemas["Severity"];
export type ChallengeStatus = Schemas["ChallengeStatus"];
export type ChallengeKind = Schemas["ChallengeKind"];
export type ContradictionStatus = Schemas["ContradictionStatus"];
export type OptionReviewStatus = Schemas["OptionReviewStatus"];
export type SourceType = Schemas["SourceType"];
export type Confidentiality = Schemas["Confidentiality"];
export type ActorKind = Schemas["ActorKind"];
export type Stance = Schemas["Stance"];

// ---- response entities ----------------------------------------------------------------------
export type Actor = Resp<Schemas["Actor"]>;
export type Scenario = Resp<Schemas["ScenarioOut"]>;
export type InvestigationSummary = Resp<Schemas["InvestigationSummary"]>;
export type InvestigationDetail = Resp<Schemas["InvestigationDetail"]>;
export type InvestigationFrame = Resp<Schemas["InvestigationFrame"]>;
export type ResearchBudget = Resp<Schemas["ResearchBudget"]>;
export type Usage = Resp<Schemas["Usage"]>;
export type RoutingDecision = Resp<Schemas["RoutingDecision"]>;
export type Hypothesis = Resp<Schemas["Hypothesis"]>;
export type ResearchTask = Resp<Schemas["ResearchTask"]>;
export type Source = Resp<Schemas["Source"]>;
export type SourceDetail = Resp<Schemas["SourceOut"]>;
export type Evidence = Resp<Schemas["Evidence"]>;
export type Claim = Resp<Schemas["Claim"]>;
export type ConfidenceAssessment = Resp<Schemas["ConfidenceAssessment"]>;
export type Finding = Resp<Schemas["Finding"]>;
export type Contradiction = Resp<Schemas["Contradiction"]>;
export type Challenge = Resp<Schemas["Challenge"]>;
export type StrategicOption = Resp<Schemas["StrategicOption"]>;
export type HumanReview = Resp<Schemas["HumanReview"]>;
export type ReviewResponse = Resp<Schemas["ReviewResponse"]>;
export type Decision = Resp<Schemas["Decision"]>;
export type IntakeDocument = Resp<Schemas["IntakeOut"]>;
export type PrivacyScanSummary = Resp<Schemas["PrivacyScanSummary"]>;
export type DataClassification = Resp<Schemas["DataClassification"]>;
export type EntityCount = Resp<Schemas["EntityCount"]>;
export type ClaimChain = Resp<Schemas["ClaimChain"]>;

// ---- request bodies -------------------------------------------------------------------------
export type CreateInvestigationBody = Schemas["CreateInvestigation"];
export type ReviewResponseBody = Schemas["ReviewResponseIn"];
export type DecisionPayload = Schemas["DecisionPayload"];
export type ClassificationOverride = Schemas["ClassificationOverride"];
export type HumanChallenge = Schemas["HumanChallenge"];
export type ItemDecision = Schemas["ItemDecision"];

// ---- shapes not described by the OpenAPI spec (see README "API gaps") ------------------------
/** GET /api/investigations/{id}/audit — served by the generic collection route as `list[Any]`. */
export interface AuditEvent {
  id: string;
  at: string;
  actor_kind: string;
  actor_id: string;
  action: string;
  subject_type: string | null;
  subject_id: string | null;
  policy_rule_id: string | null;
  summary: string;
  details: Record<string, unknown>;
}

/** GET /api/investigations/{id}/documents/{doc_id} — typed as `dict` in the spec. */
export interface DocumentDetail {
  id: string;
  title: string;
  status: string;
  scan: PrivacyScanSummary;
  sanitised_text: string;
}

export interface UploadDocumentInput {
  file: File;
  title?: string;
  sourceType: SourceType;
  confidentiality: Confidentiality;
}
