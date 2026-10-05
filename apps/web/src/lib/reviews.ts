/** Form state → `ReviewResponseIn` payload builders. Pure, so the payload shape is unit-tested. */
import type {
  Classification,
  ClassificationOverride,
  DecisionPayload,
  DecisionType,
  HumanChallenge,
  ReviewAction,
  ReviewResponseBody,
} from "./types";

/** Fields every review kind accepts (backend `_apply_common`). */
export interface CommonReviewState {
  note: string;
  challengeTargetId: string;
  challengeArgument: string;
  researchRequest: string;
  overrideClaimId: string;
  overrideClassification: Classification | "";
  overrideReason: string;
  additionalIterations: number;
}

export const EMPTY_COMMON: CommonReviewState = {
  note: "",
  challengeTargetId: "",
  challengeArgument: "",
  researchRequest: "",
  overrideClaimId: "",
  overrideClassification: "",
  overrideReason: "",
  additionalIterations: 0,
};

export const MAX_ADDITIONAL_ITERATIONS = 3;

/** Returns problems that must be fixed before the common fields can be submitted. */
export function commonProblems(s: CommonReviewState): string[] {
  const problems: string[] = [];
  const overrideStarted = Boolean(s.overrideClaimId || s.overrideClassification || s.overrideReason.trim());
  if (overrideStarted && !(s.overrideClaimId && s.overrideClassification && s.overrideReason.trim())) {
    problems.push("A classification override needs a claim, a new classification and a reason.");
  }
  if (s.challengeArgument.trim() && !s.challengeTargetId) {
    problems.push("Choose the claim (or the investigation) your challenge is aimed at.");
  }
  if (s.additionalIterations < 0 || s.additionalIterations > MAX_ADDITIONAL_ITERATIONS) {
    problems.push(`Additional iterations must be between 0 and ${MAX_ADDITIONAL_ITERATIONS}.`);
  }
  return problems;
}

export function commonPayload(s: CommonReviewState): Omit<ReviewResponseBody, "action"> {
  const challenges: HumanChallenge[] = s.challengeArgument.trim()
    ? [{ target_id: s.challengeTargetId, argument: s.challengeArgument.trim() }]
    : [];
  const overrides: ClassificationOverride[] =
    s.overrideClaimId && s.overrideClassification && s.overrideReason.trim()
      ? [{ claim_id: s.overrideClaimId, classification: s.overrideClassification, reason: s.overrideReason.trim() }]
      : [];
  return {
    note: s.note.trim() || null,
    challenges,
    classification_overrides: overrides,
    research_requests: s.researchRequest.trim() ? [s.researchRequest.trim()] : [],
    additional_iterations: s.additionalIterations,
  };
}

export function buildResponse(action: ReviewAction, common: CommonReviewState, extra: Partial<ReviewResponseBody> = {}) {
  return { action, ...commonPayload(common), ...extra } satisfies ReviewResponseBody;
}

// ---- decision ---------------------------------------------------------------------------------
export interface DecisionFormState {
  decisionType: DecisionType | "";
  statement: string;
  rationale: string;
  optionIds: string[];
  conditions: string;
  acknowledgedUnknownIds: string[];
  uncertaintiesAcknowledged: boolean;
}

export const EMPTY_DECISION: DecisionFormState = {
  decisionType: "",
  statement: "",
  rationale: "",
  optionIds: [],
  conditions: "",
  acknowledgedUnknownIds: [],
  uncertaintiesAcknowledged: false,
};

/** Option-adopting decision types must name at least one option. */
export const DECISION_TYPES_NEEDING_OPTIONS: DecisionType[] = ["adopt_option", "adopt_modified_option"];

export function decisionProblems(s: DecisionFormState, unknownIds: readonly string[]): string[] {
  const problems: string[] = [];
  if (!s.decisionType) problems.push("Choose a decision type.");
  if (!s.statement.trim()) problems.push("State the decision.");
  if (!s.rationale.trim()) problems.push("Give the rationale for the decision.");
  if (s.decisionType && DECISION_TYPES_NEEDING_OPTIONS.includes(s.decisionType) && s.optionIds.length === 0) {
    problems.push("Select the option(s) being adopted.");
  }
  const missing = unknownIds.filter((id) => !s.acknowledgedUnknownIds.includes(id));
  if (missing.length > 0) {
    problems.push(`Acknowledge each unresolved unknown (${missing.length} outstanding).`);
  }
  if (!s.uncertaintiesAcknowledged) problems.push("Acknowledge the stated uncertainties.");
  return problems;
}

export function splitLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
}

export function decisionPayload(s: DecisionFormState, unknownIds: readonly string[]): DecisionPayload {
  if (!s.decisionType) throw new Error("decision type is required");
  return {
    decision_type: s.decisionType,
    statement: s.statement.trim(),
    rationale: s.rationale.trim(),
    option_ids: [...s.optionIds],
    conditions: splitLines(s.conditions),
    uncertainties_acknowledged: s.uncertaintiesAcknowledged,
    acknowledged_unknown_claim_ids: unknownIds.filter((id) => s.acknowledgedUnknownIds.includes(id)),
  };
}

export function toggle(list: readonly string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}
