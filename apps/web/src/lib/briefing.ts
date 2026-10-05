/**
 * View-model for the Briefing page: the investigation reduced to what a single operator needs —
 * what was found, what was ruled out, what is still unknown, the options, and the decision.
 * All detail stays one click away (claim drawer / full working view).
 */
import { type CausalDriver, deriveCausalPicture } from "./causal";
import type { Claim, DecisionPayload, Evidence, HumanReview, InvestigationDetail, StrategicOption } from "./types";

/** Plain-language names for the generic driver categories. */
export const DRIVER_LABELS: Record<string, string> = {
  market_contraction: "The market itself shrank",
  share_loss: "Losing share to competitors",
  offer_proposition: "Our offer looks dated or less relevant",
  offer_format: "Our terms or format are less attractive (length, price, flexibility)",
  substitution: "Demand is moving to alternatives",
  demand_shift: "Customers' needs have changed",
  policy_change: "A policy or funding change",
  conversion: "We are converting fewer deals",
  pipeline_volume: "Fewer enquiries are coming in",
  portfolio_gap: "We don't offer what growing demand wants",
  internal_change: "An internal change (e.g. a restructure)",
  capacity: "Delivery capacity limits",
  measurement_artefact: "A change in how things are counted",
  customer_destination: "Where lost customers went",
};

export const driverLabel = (category: string) => DRIVER_LABELS[category] ?? category.replace(/_/g, " ");

const CONFIDENCE_WORDS: Record<string, string> = {
  high: "Strong evidence",
  moderate: "Reasonable evidence",
  low: "Weak evidence",
  very_low: "Very weak evidence",
};

const CONFIDENCE_ORDER = ["Very weak evidence", "Weak evidence", "Reasonable evidence", "Strong evidence"];

/** Options most worth reading first: those resting on more findings, with stronger evidence. */
export function rankOptions(options: readonly StrategicOption[]): StrategicOption[] {
  const band: Record<string, number> = { high: 3, moderate: 2, low: 1, very_low: 0 };
  return [...options].sort((a, b) =>
    b.finding_ids.length - a.finding_ids.length || (band[b.confidence_band] ?? 0) - (band[a.confidence_band] ?? 0));
}

export interface BriefingItem {
  id: string;
  label: string;
  /** Segment names where it applies (supported) or was tested (ruled out). */
  where: string[];
  /** One concrete fact from the evidence, if available. */
  fact: string | null;
  confidence: string | null;
  /** Claim to open for the full evidence chain. */
  claimId: string | null;
}

export interface UnknownItem {
  id: string;
  label: string;
  needs: string | null;
  claimId: string | null;
}

export interface Briefing {
  found: BriefingItem[];
  ruledOut: BriefingItem[];
  unknown: UnknownItem[];
}

function claimsFor(detail: InvestigationDetail, hypothesisIds: readonly string[]): Claim[] {
  const ids = new Set(hypothesisIds);
  return detail.claims.filter((c) => c.active && c.related_hypothesis_ids.some((h) => ids.has(h)));
}

const TIER_RANK: Record<string, number> = { primary: 3, secondary: 2, tertiary: 1, unsuitable: 0 };

/** The most concrete supporting fact: prefer measurements, then higher-authority sources. */
export function keyFact(claim: Claim | undefined, evidence: ReadonlyMap<string, Evidence>): string | null {
  if (!claim) return null;
  const items = claim.supporting_evidence_ids
    .map((id) => evidence.get(id))
    .filter((e): e is Evidence => Boolean(e) && !e!.flags.includes("injection_suspected"));
  items.sort(
    (a, b) =>
      Number(b.kind === "measurement") - Number(a.kind === "measurement") ||
      (TIER_RANK[b.quality?.tier ?? "tertiary"] ?? 0) - (TIER_RANK[a.quality?.tier ?? "tertiary"] ?? 0),
  );
  const best = items[0];
  if (!best) return null;
  const text = (best.quote ?? best.statement).replace(/\s+/g, " ").trim();
  return text.length > 220 ? `${text.slice(0, 217)}…` : text;
}

function toItem(detail: InvestigationDetail, d: CausalDriver, mode: "found" | "ruled_out", ev: Map<string, Evidence>,
  names: Record<string, string>): BriefingItem {
  const relevant = mode === "found" ? d.appliesIn : d.rejectedIn.length ? d.rejectedIn : d.weakenedIn;
  const hypIds = d.segmented ? relevant.map((f) => f.hypothesisId) : [d.hypothesis.id];
  const claims = claimsFor(detail, hypIds);
  // The claim that states the verdict on the driver (causal, or the "not supported" negation).
  const verdict =
    claims.find((c) => (mode === "found" ? c.causal && !c.statement.startsWith("Not supported") : c.statement.startsWith("Not supported"))) ??
    claims[0];
  return {
    id: d.hypothesis.id,
    label: driverLabel(d.category),
    where: d.segmented ? relevant.map((f) => names[f.segment] ?? f.segment) : [],
    fact: keyFact(verdict, ev),
    confidence: verdict?.confidence ? CONFIDENCE_WORDS[verdict.confidence.band] ?? null : null,
    claimId: verdict?.id ?? null,
  };
}

export function buildBriefing(detail: InvestigationDetail): Briefing {
  const picture = deriveCausalPicture(detail.hypotheses);
  const ev = new Map(detail.evidence.map((e) => [e.id, e]));
  const names = detail.segment_names ?? {};
  const strength = (i: BriefingItem) => CONFIDENCE_ORDER.indexOf(i.confidence ?? "") * 10 + (i.where.length ? 1 : 0);
  const found = picture.supported.map((d) => toItem(detail, d, "found", ev, names)).sort((a, b) => strength(b) - strength(a));
  // The confidence word belongs to the "not supported" claim; on a ruled-out line it reads as doubt, so omit it.
  const ruledOut = picture.rejected.map((d) => ({ ...toItem(detail, d, "ruled_out", ev, names), confidence: null }));

  const unknown: UnknownItem[] = [];
  const seen = new Set<string>();
  for (const c of detail.claims) {
    if (!c.active || c.classification !== "unknown") continue;
    const h = detail.hypotheses.find((x) => c.related_hypothesis_ids.includes(x.id));
    const key = h?.id ?? c.id;
    seen.add(key);
    unknown.push({
      id: c.id,
      label: h ? driverLabel(h.category) : c.statement,
      needs: c.missing_evidence[0] ? simplifyNeed(c.missing_evidence[0]) : null,
      claimId: c.id,
    });
  }
  for (const d of picture.open) {
    if (seen.has(d.hypothesis.id)) continue;
    unknown.push({ id: d.hypothesis.id, label: driverLabel(d.category), needs: "Not enough evidence was found either way.",
      claimId: null });
  }
  return { found, ruledOut, unknown };
}

/** "No dataset with role 'customer_destination' is available. …" -> "Needs customer destination data." */
export function simplifyNeed(text: string): string {
  const m = text.match(/role '([a-z_]+)'/);
  if (m) return `Needs ${m[1].replace(/_/g, " ")} data (e.g. a survey of lost customers), which we don't have.`;
  return text.length > 160 ? `${text.slice(0, 157)}…` : text;
}

// ---- progress --------------------------------------------------------------------------------

export type StepState = "done" | "active" | "waiting" | "todo";

export interface ProgressStep {
  label: string;
  state: StepState;
}

export function progress(detail: InvestigationDetail): { steps: ProgressStep[]; line: string } {
  const s = detail.summary.status;
  const pending = detail.reviews.find((r) => r.id === detail.pending_review_id && r.status === "pending");
  const max = detail.budget?.max_iterations ?? 0;
  const researched = detail.iteration > 0;
  const hasOptions = detail.options.length > 0;
  const decided = s === "decided" || detail.decision != null;

  const step = (done: boolean, active: boolean, waiting = false): StepState =>
    done ? "done" : waiting ? "waiting" : active ? "active" : "todo";
  const privacyPending = pending?.kind === "privacy_release";
  const steps: ProgressStep[] = [
    { label: "Understand the question", state: step(Boolean(detail.frame), s === "running" && !detail.frame) },
    { label: "Release confidential documents", state: step(researched || detail.hypotheses.length > 0, false, privacyPending) },
    { label: researched ? `Research (round ${detail.iteration} of ${max})` : "Research", state: step(hasOptions, s === "running" && !hasOptions && !privacyPending, pending?.kind === "findings") },
    { label: "Draft options", state: step(hasOptions && pending?.kind !== "options", false, pending?.kind === "options") },
    { label: "Your decision", state: step(decided, false, pending?.kind === "decision") },
  ];
  const line =
    s === "draft" ? "Not started" :
    s === "running" ? "The agents are working…" :
    s === "awaiting_review" || s === "awaiting_decision" ? "Waiting for you" :
    s === "decided" ? "Decided" :
    s === "failed" ? "Something went wrong" : "Closed";
  return { steps, line };
}

// ---- decision --------------------------------------------------------------------------------

export const RESEARCH_FIRST = "__research_first__";

export function decisionOptions(detail: InvestigationDetail, review: HumanReview | undefined): StrategicOption[] {
  const ids = new Set(review?.subject_ids ?? []);
  return detail.options.filter((o) => ids.has(o.id));
}

export function simpleDecisionPayload(choice: string, why: string, option: StrategicOption | undefined,
  unknownIds: readonly string[]): DecisionPayload {
  const research = choice === RESEARCH_FIRST || !option;
  return {
    decision_type: research ? "commission_further_investigation" : "adopt_option",
    statement: research ? "Research the unknowns before committing to a change." : `Adopt: ${option!.title}`,
    rationale: why.trim(),
    option_ids: research ? [] : [option!.id],
    conditions: [],
    uncertainties_acknowledged: true,
    acknowledged_unknown_claim_ids: [...unknownIds],
  };
}
