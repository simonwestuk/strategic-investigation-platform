/**
 * `HumanReview.context` is an untyped dict in the API. These parsers narrow it per review kind,
 * tolerating missing fields so a backend change degrades the form rather than crashing it.
 */
import type { DataClassification, EntityCount } from "./types";

type Dict = Record<string, unknown>;

const isDict = (v: unknown): v is Dict => typeof v === "object" && v !== null && !Array.isArray(v);
const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const num = (v: unknown, fallback = 0): number => (typeof v === "number" ? v : fallback);
const strList = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);
const dictList = (v: unknown): Dict[] => (Array.isArray(v) ? v.filter(isDict) : []);

export interface PrivacyDocumentCard {
  id: string;
  title: string;
  kind: string;
  filename: string;
  classification: DataClassification;
  entityCounts: EntityCount[];
  lowConfidenceDetections: number;
  specialCategoryTypes: string[];
  confidentialityMarkers: string[];
  sanitisedPreview: string;
  policyRule: string;
  policyReason: string;
}

function parseClassification(v: unknown): DataClassification {
  const d = isDict(v) ? v : {};
  return {
    confidentiality: (str(d.confidentiality, "internal") as DataClassification["confidentiality"]),
    personal_data: (str(d.personal_data, "none") as DataClassification["personal_data"]),
    pseudonymised: d.pseudonymised === true,
  };
}

export function parsePrivacyContext(ctx: Dict): PrivacyDocumentCard[] {
  return dictList(ctx.documents).map((d) => ({
    id: str(d.id),
    title: str(d.title, str(d.filename, "Untitled document")),
    kind: str(d.kind, "document"),
    filename: str(d.filename),
    classification: parseClassification(d.classification),
    entityCounts: dictList(d.entity_counts).map((e) => ({
      entity_type: str(e.entity_type) as EntityCount["entity_type"],
      count: num(e.count),
      low_confidence: num(e.low_confidence),
    })),
    lowConfidenceDetections: num(d.low_confidence_detections),
    specialCategoryTypes: strList(d.special_category_types),
    confidentialityMarkers: strList(d.confidentiality_markers),
    sanitisedPreview: str(d.sanitised_preview),
    policyRule: str(d.policy_rule),
    policyReason: str(d.policy_reason),
  }));
}

export interface ContextOption {
  id: string;
  title: string;
  consequence?: string;
  confidenceBand?: string;
}

export function parseContextOptions(ctx: Dict): ContextOption[] {
  return dictList(ctx.options).map((o) => ({
    id: str(o.id),
    title: str(o.title, str(o.id)),
    consequence: typeof o.consequence === "string" ? o.consequence : undefined,
    confidenceBand: typeof o.confidence_band === "string" ? o.confidence_band : undefined,
  }));
}

export interface DecisionContext {
  options: ContextOption[];
  unknowns: { id: string; statement: string }[];
  decisionTypes: string[];
}

export function parseDecisionContext(ctx: Dict): DecisionContext {
  return {
    options: parseContextOptions(ctx),
    unknowns: dictList(ctx.unknowns_to_acknowledge).map((u) => ({ id: str(u.id), statement: str(u.statement) })),
    decisionTypes: strList(ctx.decision_types),
  };
}

export interface FindingsContext {
  openBlockingChallenges: { id: string; kind: string; targetId: string; argument: string }[];
  findings: { id: string; statement: string }[];
  stopReason: string | null;
}

export function parseFindingsContext(ctx: Dict): FindingsContext {
  return {
    openBlockingChallenges: dictList(ctx.open_blocking_challenges).map((c) => ({
      id: str(c.id),
      kind: str(c.kind),
      targetId: str(c.target_id),
      argument: str(c.argument),
    })),
    findings: dictList(ctx.findings).map((f) => ({ id: str(f.id), statement: str(f.statement) })),
    stopReason: typeof ctx.stop_reason === "string" ? ctx.stop_reason : null,
  };
}

export interface ClarificationContext {
  questions: string[];
  subject: string;
}

export function parseClarificationContext(ctx: Dict): ClarificationContext {
  return { questions: strList(ctx.questions), subject: str(ctx.subject) };
}
