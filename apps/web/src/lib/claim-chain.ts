import type { ClaimChain, InvestigationDetail } from "./types";

/**
 * Client-side equivalent of `GET /claims/{id}` (same selection rules as the backend route).
 * Used in fixture mode, where only one claim chain was captured from the live API.
 */
export function deriveClaimChain(detail: InvestigationDetail, claimId: string): ClaimChain | null {
  const claim = detail.claims.find((c) => c.id === claimId);
  if (!claim) return null;
  const ids = new Set([...claim.supporting_evidence_ids, ...claim.contradicting_evidence_ids]);
  const evidence = detail.evidence.filter((e) => ids.has(e.id));
  const sourceIds = new Set(evidence.map((e) => e.source_id));
  const sources = detail.sources.filter((s) => sourceIds.has(s.id));
  const findings = detail.findings.filter((f) => f.claim_ids.includes(claim.id));
  const findingIds = new Set(findings.map((f) => f.id));
  const options = detail.options.filter(
    (o) => o.claim_ids.includes(claim.id) || o.finding_ids.some((fid) => findingIds.has(fid)),
  );
  const challenges = detail.challenges.filter((c) => c.target_id === claim.id);
  return { claim, evidence, sources, findings, options, challenges };
}
