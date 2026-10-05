import { describe, expect, it } from "vitest";
import decided from "../../../fixtures/investigation-decided.json";
import { RESEARCH_FIRST, buildBriefing, rankOptions, simpleDecisionPayload, simplifyNeed } from "../briefing";
import type { InvestigationDetail, StrategicOption } from "../types";

const detail = decided as unknown as InvestigationDetail;

describe("briefing", () => {
  const b = buildBriefing(detail);

  it("separates what was found, ruled out and unknown in plain language", () => {
    expect(b.found.map((f) => f.label)).toContain("Losing share to competitors");
    expect(b.ruledOut.map((f) => f.label)).toContain("An internal change (e.g. a restructure)");
    expect(b.unknown.map((u) => u.label)).toContain("Where lost customers went");
  });

  it("names segments rather than codes and links each line to evidence", () => {
    const share = b.found.find((f) => f.label === "Losing share to competitors")!;
    expect(share.where).toEqual(["Digital & Technology Solutions Professional"]);
    expect(share.claimId).toBeTruthy();
    expect(share.fact).toMatch(/620/);
  });

  it("does not show an evidence-strength word on ruled-out lines", () => {
    expect(b.ruledOut.every((r) => r.confidence === null)).toBe(true);
  });

  it("explains missing data simply", () => {
    expect(simplifyNeed("No dataset with role 'customer_destination' is available.")).toMatch(/customer destination data/);
  });

  it("ranks options by the evidence behind them", () => {
    const ranked = rankOptions(detail.options);
    expect(ranked[0].finding_ids.length).toBeGreaterThanOrEqual(ranked.at(-1)!.finding_ids.length);
  });

  it("builds a valid decision payload for both choices", () => {
    const option = detail.options[0] as StrategicOption;
    const adopt = simpleDecisionPayload(option.id, "Because.", option, ["clm_1"]);
    expect(adopt).toMatchObject({ decision_type: "adopt_option", option_ids: [option.id], uncertainties_acknowledged: true,
      acknowledged_unknown_claim_ids: ["clm_1"] });
    const research = simpleDecisionPayload(RESEARCH_FIRST, "Not enough evidence.", undefined, []);
    expect(research).toMatchObject({ decision_type: "commission_further_investigation", option_ids: [] });
  });
});
