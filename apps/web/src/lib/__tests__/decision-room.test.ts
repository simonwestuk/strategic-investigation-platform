import { describe, expect, it } from "vitest";
import { awaitingDecisionFixture as detail } from "@/test/fixtures";
import { deriveClaimChain } from "../claim-chain";
import { bucketKnowledge, buildLookups, furtherInvestigation, optionChain } from "../decision-room";
import { claimChainFixture } from "@/test/fixtures";

describe("bucketKnowledge", () => {
  it("splits active claims by classification and surfaces open conflicts", () => {
    const b = bucketKnowledge(detail);
    expect(b.known.every((c) => c.classification === "known")).toBe(true);
    expect(b.inferred.every((c) => c.classification === "inferred")).toBe(true);
    expect(b.unknown.map((c) => c.classification)).toEqual(["unknown", "hypothesis"]);
    expect(b.unresolvedHypotheses.map((h) => h.category).sort()).toEqual(["capacity", "customer_destination"]);
    expect(b.contradictions.every((c) => c.status === "unresolved")).toBe(true);
    expect(b.openChallenges.every((c) => c.status === "open")).toBe(true);
    const active = detail.claims.filter((c) => c.active).length;
    expect(b.known.length + b.inferred.length + b.unknown.length).toBe(active);
  });
});

describe("furtherInvestigation", () => {
  it("lists unknown claims' gaps and blocked research tasks", () => {
    const items = furtherInvestigation(detail);
    expect(items.map((i) => i.kind).sort()).toEqual(["blocked_task", "unknown_claim"]);
    expect(items.find((i) => i.kind === "blocked_task")?.needs[0]).toMatch(/customer_destination/);
  });
});

describe("optionChain", () => {
  it("walks option → finding → claim → evidence → source", () => {
    const lk = buildLookups(detail);
    const chain = optionChain(detail.options[0], lk);
    expect(chain.findings).toHaveLength(1);
    const claim = chain.findings[0].claims[0];
    expect(claim.claim.id).toBe("clm_f7d624b3aa");
    expect(claim.evidence.length).toBe(4);
    expect(claim.evidence.every((e) => e.source !== undefined)).toBe(true);
    expect(chain.directClaims).toHaveLength(0);
  });
});

describe("deriveClaimChain", () => {
  it("matches the backend's /claims/{id} response for the captured claim", () => {
    const derived = deriveClaimChain(detail, claimChainFixture.claim.id)!;
    expect(derived.evidence.map((e) => e.id).sort()).toEqual(claimChainFixture.evidence.map((e) => e.id).sort());
    expect(derived.sources.map((s) => s.id).sort()).toEqual(claimChainFixture.sources.map((s) => s.id).sort());
    expect(derived.findings.map((f) => f.id)).toEqual(claimChainFixture.findings.map((f) => f.id));
    expect(derived.options.map((o) => o.id).sort()).toEqual(claimChainFixture.options.map((o) => o.id).sort());
  });
});
