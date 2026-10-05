/** View-model derivations for the Decision Room. Pure functions over the workspace payload. */
import type {
  Challenge,
  Claim,
  Contradiction,
  Evidence,
  Finding,
  Hypothesis,
  InvestigationDetail,
  Source,
  StrategicOption,
} from "./types";

export interface KnowledgeBuckets {
  known: Claim[];
  inferred: Claim[];
  /** UNKNOWN claims first, then HYPOTHESIS-classified claims (not established). */
  unknown: Claim[];
  unresolvedHypotheses: Hypothesis[];
  contradictions: Contradiction[];
  openChallenges: Challenge[];
}

const byConfidence = (a: Claim, b: Claim) => (b.confidence?.score ?? 0) - (a.confidence?.score ?? 0);

export function bucketKnowledge(detail: InvestigationDetail): KnowledgeBuckets {
  const active = detail.claims.filter((c) => c.active);
  const of = (cls: Claim["classification"]) => active.filter((c) => c.classification === cls).sort(byConfidence);
  return {
    known: of("known"),
    inferred: of("inferred"),
    unknown: [...of("unknown"), ...of("hypothesis")],
    unresolvedHypotheses: detail.hypotheses.filter(
      (h) => h.status === "unresolved" || h.status === "investigating" || h.status === "proposed",
    ),
    contradictions: detail.contradictions.filter((c) => c.status === "unresolved"),
    openChallenges: detail.challenges.filter((c) => c.status === "open"),
  };
}

export interface FurtherInvestigationItem {
  id: string;
  kind: "unknown_claim" | "blocked_task";
  title: string;
  needs: string[];
  nextQuestion: string | null;
  claimId?: string;
}

export function furtherInvestigation(detail: InvestigationDetail): FurtherInvestigationItem[] {
  const items: FurtherInvestigationItem[] = [];
  for (const c of detail.claims) {
    if (!c.active || c.classification !== "unknown") continue;
    items.push({
      id: c.id,
      kind: "unknown_claim",
      title: c.statement,
      needs: c.missing_evidence,
      nextQuestion: c.next_question,
      claimId: c.id,
    });
  }
  for (const t of detail.tasks) {
    if (t.status !== "blocked_unavailable") continue;
    items.push({
      id: t.id,
      kind: "blocked_task",
      title: t.question,
      needs: [t.status_reason || t.required_evidence].filter(Boolean),
      nextQuestion: null,
    });
  }
  return items;
}

// ---- option → finding → claim → evidence → source -------------------------------------------
export interface EvidenceLink {
  evidence: Evidence;
  source: Source | undefined;
  stance: "supports" | "contradicts";
}

export interface ClaimLink {
  claim: Claim;
  evidence: EvidenceLink[];
}

export interface FindingLink {
  finding: Finding;
  claims: ClaimLink[];
}

export interface OptionChain {
  findings: FindingLink[];
  /** Claims cited by the option directly but not reached through a finding. */
  directClaims: ClaimLink[];
}

export interface Lookups {
  claims: Map<string, Claim>;
  evidence: Map<string, Evidence>;
  sources: Map<string, Source>;
  findings: Map<string, Finding>;
  hypotheses: Map<string, Hypothesis>;
  options: Map<string, StrategicOption>;
}

export function buildLookups(detail: InvestigationDetail): Lookups {
  const index = <T extends { id: string }>(xs: readonly T[]) => new Map(xs.map((x) => [x.id, x]));
  return {
    claims: index(detail.claims),
    evidence: index(detail.evidence),
    sources: index(detail.sources),
    findings: index(detail.findings),
    hypotheses: index(detail.hypotheses),
    options: index(detail.options),
  };
}

export function claimLink(claim: Claim, lk: Lookups): ClaimLink {
  const ev = (ids: string[], stance: EvidenceLink["stance"]): EvidenceLink[] =>
    ids
      .map((id) => lk.evidence.get(id))
      .filter((e): e is Evidence => Boolean(e))
      .map((e) => ({ evidence: e, source: lk.sources.get(e.source_id), stance }));
  return {
    claim,
    evidence: [...ev(claim.supporting_evidence_ids, "supports"), ...ev(claim.contradicting_evidence_ids, "contradicts")],
  };
}

export function optionChain(option: StrategicOption, lk: Lookups): OptionChain {
  const reached = new Set<string>();
  const findings: FindingLink[] = option.finding_ids
    .map((id) => lk.findings.get(id))
    .filter((f): f is Finding => Boolean(f))
    .map((finding) => ({
      finding,
      claims: finding.claim_ids
        .map((cid) => lk.claims.get(cid))
        .filter((c): c is Claim => Boolean(c))
        .map((c) => {
          reached.add(c.id);
          return claimLink(c, lk);
        }),
    }));
  const directClaims = option.claim_ids
    .filter((id) => !reached.has(id))
    .map((id) => lk.claims.get(id))
    .filter((c): c is Claim => Boolean(c))
    .map((c) => claimLink(c, lk));
  return { findings, directClaims };
}

/** Claims linked to a hypothesis (via `related_hypothesis_ids`). */
export function claimsForHypothesis(claims: readonly Claim[], hypothesisId: string): Claim[] {
  return claims.filter((c) => c.active && c.related_hypothesis_ids.includes(hypothesisId));
}

export function evidenceStanceCounts(evidence: readonly Evidence[], hypothesisId: string) {
  let supports = 0;
  let contradicts = 0;
  for (const e of evidence) {
    for (const l of e.links) {
      if (l.hypothesis_id !== hypothesisId) continue;
      if (l.stance === "supports") supports += 1;
      else if (l.stance === "contradicts") contradicts += 1;
    }
  }
  return { supports, contradicts };
}
