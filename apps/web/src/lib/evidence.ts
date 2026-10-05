import type { AuthorityTier, Evidence, EvidenceKind, Freshness, QuoteVerification, Source } from "./types";

export interface EvidenceFilter {
  text: string;
  kind: EvidenceKind | "all";
  tier: AuthorityTier | "all";
  freshness: Freshness | "all";
  verification: QuoteVerification | "all";
  flag: "all" | "any" | "none" | string;
  origin: "all" | "external_web" | "internal" | "human";
}

export const DEFAULT_EVIDENCE_FILTER: EvidenceFilter = {
  text: "",
  kind: "all",
  tier: "all",
  freshness: "all",
  verification: "all",
  flag: "all",
  origin: "all",
};

/** Flags on the evidence item plus injection flags raised on its source. */
export function evidenceFlags(e: Evidence, source: Source | undefined): string[] {
  return [...new Set([...e.flags, ...(source?.injection_flags.length ? ["injection_suspected"] : [])])];
}

export function filterEvidence(
  evidence: readonly Evidence[],
  sources: ReadonlyMap<string, Source>,
  f: EvidenceFilter,
): Evidence[] {
  const q = f.text.trim().toLowerCase();
  return evidence.filter((e) => {
    const src = sources.get(e.source_id);
    if (f.kind !== "all" && e.kind !== f.kind) return false;
    if (f.tier !== "all" && e.quality?.tier !== f.tier) return false;
    if (f.freshness !== "all" && e.quality?.freshness !== f.freshness) return false;
    if (f.verification !== "all" && e.verification !== f.verification) return false;
    if (f.origin !== "all" && src?.origin !== f.origin) return false;
    const flags = evidenceFlags(e, src);
    if (f.flag === "any" && flags.length === 0) return false;
    if (f.flag === "none" && flags.length > 0) return false;
    if (f.flag !== "all" && f.flag !== "any" && f.flag !== "none" && !flags.includes(f.flag)) return false;
    if (q) {
      const hay = [e.statement, e.quote ?? "", src?.title ?? "", src?.publisher ?? "", e.segments.join(" ")]
        .join(" ")
        .toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export const TIER_ORDER: AuthorityTier[] = ["primary", "secondary", "tertiary", "unsuitable"];
export const FRESHNESS_ORDER: Freshness[] = ["current", "ageing", "stale", "undated"];
