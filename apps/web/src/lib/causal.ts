/**
 * Derives the "likely causal picture" from the hypothesis tree.
 *
 * Top-level hypotheses are candidate drivers. A driver whose evidence diverged by segment is
 * marked `split` and refined into segment children; its verdict comes from those children, so a
 * driver can apply in one segment and be rejected in another.
 */
import type { Hypothesis, HypothesisStatus } from "./types";

export type SegmentVerdict = "supported" | "rejected" | "weakened" | "open";
export type DriverVerdict = SegmentVerdict | "mixed";

export interface SegmentFinding {
  hypothesisId: string;
  segment: string;
  verdict: SegmentVerdict;
  status: HypothesisStatus;
  statement: string;
  reason: string;
}

export interface CausalDriver {
  hypothesis: Hypothesis;
  category: string;
  verdict: DriverVerdict;
  /** True when the driver was refined into segment children. */
  segmented: boolean;
  appliesIn: SegmentFinding[];
  rejectedIn: SegmentFinding[];
  weakenedIn: SegmentFinding[];
  openIn: SegmentFinding[];
}

export interface CausalPicture {
  /** Supported everywhere tested, or in at least one segment. */
  supported: CausalDriver[];
  /** Contradicted (everywhere tested) or weakened. */
  rejected: CausalDriver[];
  /** Not yet resolved by the evidence. */
  open: CausalDriver[];
  /** All segment codes that appear in the tree, sorted. */
  segments: string[];
}

export function segmentVerdict(status: HypothesisStatus): SegmentVerdict {
  switch (status) {
    case "supported":
      return "supported";
    case "contradicted":
      return "rejected";
    case "weakened":
      return "weakened";
    default:
      return "open";
  }
}

function toSegmentFinding(h: Hypothesis): SegmentFinding {
  return {
    hypothesisId: h.id,
    segment: h.segment ?? "All segments",
    verdict: segmentVerdict(h.status),
    status: h.status,
    statement: h.statement,
    reason: h.status_reason,
  };
}

function combine(children: SegmentFinding[]): DriverVerdict {
  const has = (v: SegmentVerdict) => children.some((c) => c.verdict === v);
  if (has("supported") && (has("rejected") || has("weakened"))) return "mixed";
  if (has("supported")) return "supported";
  if (children.length > 0 && children.every((c) => c.verdict === "rejected")) return "rejected";
  if (has("weakened") && !has("open")) return "weakened";
  if (has("rejected") && !has("open")) return "rejected";
  return "open";
}

export function buildDriver(parent: Hypothesis, children: Hypothesis[]): CausalDriver {
  const segmented = parent.status === "split" && children.length > 0;
  const findings = segmented ? children.map(toSegmentFinding) : [toSegmentFinding(parent)];
  const verdict: DriverVerdict = segmented ? combine(findings) : segmentVerdict(parent.status);
  const by = (v: SegmentVerdict) =>
    findings.filter((f) => f.verdict === v).sort((a, b) => a.segment.localeCompare(b.segment));
  return {
    hypothesis: parent,
    category: parent.category,
    verdict,
    segmented,
    appliesIn: by("supported"),
    rejectedIn: by("rejected"),
    weakenedIn: by("weakened"),
    openIn: by("open"),
  };
}

export function deriveCausalPicture(hypotheses: readonly Hypothesis[]): CausalPicture {
  const childrenOf = new Map<string, Hypothesis[]>();
  for (const h of hypotheses) {
    if (h.parent_id) childrenOf.set(h.parent_id, [...(childrenOf.get(h.parent_id) ?? []), h]);
  }
  const ids = new Set(hypotheses.map((h) => h.id));
  // Roots are hypotheses without a parent (or whose parent is not in the payload).
  const roots = hypotheses.filter((h) => !h.parent_id || !ids.has(h.parent_id));
  const drivers = roots.map((r) => buildDriver(r, childrenOf.get(r.id) ?? []));

  const segments = [
    ...new Set(hypotheses.map((h) => h.segment).filter((s): s is string => Boolean(s))),
  ].sort();

  return {
    supported: drivers.filter((d) => d.verdict === "supported" || d.verdict === "mixed"),
    rejected: drivers.filter((d) => d.verdict === "rejected" || d.verdict === "weakened"),
    open: drivers.filter((d) => d.verdict === "open"),
    segments,
  };
}
