import type {
  Classification,
  ConfidenceBand,
  DecisionType,
  HypothesisStatus,
  OptionReviewStatus,
} from "./types";

export interface ClassificationMeta {
  label: string;
  glyph: string;
  description: string;
}

/** Order is epistemic strength: what is established first, what is missing last. */
export const CLASSIFICATION_ORDER: Classification[] = ["known", "inferred", "hypothesis", "unknown"];

export const CLASSIFICATION_META: Record<Classification, ClassificationMeta> = {
  known: {
    label: "KNOWN",
    glyph: "■",
    description: "Directly established by authoritative, current evidence.",
  },
  inferred: {
    label: "INFERRED",
    glyph: "◩",
    description: "Follows from the evidence through a stated inferential step.",
  },
  hypothesis: {
    label: "HYPOTHESIS",
    glyph: "◇",
    description: "Plausible but not established; evidence is weak, stale or one-sided.",
  },
  unknown: {
    label: "UNKNOWN",
    glyph: "?",
    description: "Cannot be determined from the available evidence.",
  },
};

export const CONFIDENCE_LABELS: Record<ConfidenceBand, string> = {
  high: "High",
  moderate: "Moderate",
  low: "Low",
  very_low: "Very low",
};

/** Number of filled pips (of 4) for a confidence band. */
export const CONFIDENCE_PIPS: Record<ConfidenceBand, number> = { high: 4, moderate: 3, low: 2, very_low: 1 };

export const HYPOTHESIS_STATUS_LABELS: Record<HypothesisStatus, string> = {
  proposed: "Proposed",
  investigating: "Investigating",
  supported: "Supported",
  weakened: "Weakened",
  contradicted: "Contradicted",
  unresolved: "Unresolved",
  split: "Split by segment",
};

export const OPTION_REVIEW_LABELS: Record<OptionReviewStatus, string> = {
  draft: "Draft",
  pending_review: "Pending governance review",
  approved_for_decision: "Approved for decision",
  modified: "Modified by reviewer",
  rejected: "Rejected by reviewer",
};

export const DECISION_TYPE_LABELS: Record<DecisionType, string> = {
  adopt_option: "Adopt option(s)",
  adopt_modified_option: "Adopt a modified option",
  commission_further_investigation: "Commission further investigation",
  defer: "Defer the decision",
  reject_all_options: "Reject all options",
};

export const STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  running: "Running",
  awaiting_review: "Awaiting review",
  awaiting_decision: "Awaiting decision",
  decided: "Decided",
  closed: "Closed",
  failed: "Failed",
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}
