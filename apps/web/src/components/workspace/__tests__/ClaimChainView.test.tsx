import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { awaitingDecisionFixture, claimChainFixture } from "@/test/fixtures";
import type { ClaimChain } from "@/lib/types";
import { ClaimChainView } from "../ClaimChainView";

describe("ClaimChainView", () => {
  it("renders the claim, rubric and evidence → source chain from claim-chain.json", async () => {
    const onOpenSource = vi.fn();
    render(<ClaimChainView chain={claimChainFixture} onOpenSource={onOpenSource} />);
    const { claim } = claimChainFixture;

    expect(screen.getByTestId("claim-statement")).toHaveTextContent(claim.statement);
    expect(screen.getAllByRole("img", { name: "Classification: INFERRED" }).length).toBeGreaterThan(0);
    // Confidence rubric factors and ceiling reasons.
    for (const f of claim.confidence!.factors) expect(screen.getByText(f)).toBeInTheDocument();
    for (const r of claim.confidence!.ceiling_reasons) expect(screen.getByText(r)).toBeInTheDocument();
    expect(screen.getByText(claim.inferential_step!)).toBeInTheDocument();
    expect(screen.getByText(claim.missing_evidence[0])).toBeInTheDocument();

    // All four supporting evidence items, each with its source.
    const supporting = screen.getByText(/Supporting evidence \(4\)/).closest("section")!;
    expect(within(supporting).getAllByText("Supports")).toHaveLength(4);
    const firstSource = claimChainFixture.sources[0];
    const sourceButtons = within(supporting).getAllByRole("button", { name: firstSource.title });
    await userEvent.click(sourceButtons[0]);
    expect(onOpenSource).toHaveBeenCalledWith(firstSource.id);
    expect(within(supporting).getAllByText("synthetic").length).toBeGreaterThan(0);

    // Linked findings and options; options are labelled as AI recommendations.
    expect(screen.getByText(/Findings built on this claim \(1\)/)).toBeInTheDocument();
    const options = screen.getByText(/Strategic options citing it \(2\)/).closest("section")!;
    expect(within(options).getAllByText(/AI recommendation · not a decision/)).toHaveLength(2);
    expect(screen.getByText(/No challenges raised/)).toBeInTheDocument();
    expect(screen.getByText(/No human override/)).toBeInTheDocument();
  });

  it("explains a rubric downgrade from the proposed classification", () => {
    const capped = awaitingDecisionFixture.claims.find((c) => c.classification !== c.proposed_classification)!;
    const chain: ClaimChain = { claim: capped, evidence: [], sources: [], findings: [], options: [], challenges: [] };
    render(<ClaimChainView chain={chain} onOpenSource={() => {}} />);
    expect(screen.getByRole("note")).toHaveTextContent(/downgraded this claim from INFERRED to HYPOTHESIS/);
    expect(screen.getByText("All supporting evidence is stale relative to the as-of date.")).toBeInTheDocument();
  });

  it("shows a human override with who made it", () => {
    const claim = {
      ...claimChainFixture.claim,
      classification: "hypothesis" as const,
      human_override: {
        actor: { kind: "human" as const, id: "dev:gareth", display_name: "Gareth Lewis", roles: ["governance_reviewer" as const] },
        previous: "inferred" as const,
        new: "hypothesis" as const,
        reason: "Competitor evidence is anecdotal",
        at: "2026-10-05T10:30:00Z",
      },
    };
    render(<ClaimChainView chain={{ ...claimChainFixture, claim }} onOpenSource={() => {}} />);
    expect(screen.getByText("Gareth Lewis")).toBeInTheDocument();
    expect(screen.getByText(/Competitor evidence is anecdotal/)).toBeInTheDocument();
  });
});
