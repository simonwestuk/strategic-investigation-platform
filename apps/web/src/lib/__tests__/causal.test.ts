import { describe, expect, it } from "vitest";
import { awaitingDecisionFixture } from "@/test/fixtures";
import { deriveCausalPicture } from "../causal";
import type { Hypothesis } from "../types";

const base = awaitingDecisionFixture.hypotheses[0];
const hyp = (over: Partial<Hypothesis>): Hypothesis => ({ ...base, parent_id: null, segment: null, ...over });

describe("deriveCausalPicture", () => {
  it("derives segment-level verdicts from the real hypothesis tree", () => {
    const picture = deriveCausalPicture(awaitingDecisionFixture.hypotheses);
    expect(picture.segments).toEqual(["DSP6", "DTS6", "SL7"]);

    const byCategory = (c: string) =>
      [...picture.supported, ...picture.rejected, ...picture.open].find((d) => d.category === c)!;

    // Split parent: market contraction applies to DSP6 and SL7 but was rejected for DTS6.
    const market = byCategory("market_contraction");
    expect(market.segmented).toBe(true);
    expect(market.verdict).toBe("mixed");
    expect(market.appliesIn.map((f) => f.segment)).toEqual(["DSP6", "SL7"]);
    expect(market.rejectedIn.map((f) => f.segment)).toEqual(["DTS6"]);

    // Share loss is the mirror image.
    const share = byCategory("share_loss");
    expect(share.appliesIn.map((f) => f.segment)).toEqual(["DTS6"]);
    expect(share.rejectedIn.map((f) => f.segment)).toEqual(["SL7"]);

    // Mixed drivers count as supported (they apply somewhere).
    expect(picture.supported.map((d) => d.category)).toContain("market_contraction");
    // Unsplit drivers: contradicted / weakened are rejected; unresolved stay open.
    expect(picture.rejected.map((d) => d.category)).toEqual(
      expect.arrayContaining(["internal_change", "measurement_artefact"]),
    );
    expect(picture.open.map((d) => d.category).sort()).toEqual(["capacity", "customer_destination"]);
  });

  it("never lists a segment child as a top-level driver", () => {
    const picture = deriveCausalPicture(awaitingDecisionFixture.hypotheses);
    const all = [...picture.supported, ...picture.rejected, ...picture.open];
    expect(all.every((d) => d.hypothesis.parent_id === null)).toBe(true);
    expect(all).toHaveLength(14);
  });

  it("treats a split driver rejected in every segment as rejected", () => {
    const picture = deriveCausalPicture([
      hyp({ id: "p", status: "split", category: "policy" }),
      hyp({ id: "a", parent_id: "p", segment: "A", status: "contradicted" }),
      hyp({ id: "b", parent_id: "p", segment: "B", status: "contradicted" }),
    ]);
    expect(picture.rejected).toHaveLength(1);
    expect(picture.rejected[0].verdict).toBe("rejected");
    expect(picture.rejected[0].rejectedIn).toHaveLength(2);
  });

  it("keeps a split driver open while any segment is untested and none supports it", () => {
    const picture = deriveCausalPicture([
      hyp({ id: "p", status: "split" }),
      hyp({ id: "a", parent_id: "p", segment: "A", status: "contradicted" }),
      hyp({ id: "b", parent_id: "p", segment: "B", status: "investigating" }),
    ]);
    expect(picture.open).toHaveLength(1);
    expect(picture.open[0].openIn.map((f) => f.segment)).toEqual(["B"]);
  });

  it("treats a portfolio-wide supported driver as supported in all segments", () => {
    const picture = deriveCausalPicture([hyp({ id: "x", status: "supported" })]);
    expect(picture.supported[0].segmented).toBe(false);
    expect(picture.supported[0].appliesIn[0].segment).toBe("All segments");
  });
});
