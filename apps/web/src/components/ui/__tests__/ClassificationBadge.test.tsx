import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ClassificationBadge } from "../ClassificationBadge";

describe("ClassificationBadge", () => {
  it.each([
    ["known", "KNOWN"],
    ["inferred", "INFERRED"],
    ["hypothesis", "HYPOTHESIS"],
    ["unknown", "UNKNOWN"],
  ] as const)("renders a text label for %s (not colour alone)", (classification, label) => {
    render(<ClassificationBadge classification={classification} />);
    const badge = screen.getByRole("img", { name: `Classification: ${label}` });
    expect(badge).toHaveTextContent(label);
    expect(badge).toHaveAttribute("data-classification", classification);
    expect(badge).toHaveAttribute("title");
  });

  it("draws UNKNOWN with a dashed outline and HYPOTHESIS with a dotted one", () => {
    const { rerender } = render(<ClassificationBadge classification="unknown" />);
    expect(screen.getByRole("img")).toHaveClass("border-dashed");
    rerender(<ClassificationBadge classification="hypothesis" />);
    expect(screen.getByRole("img")).toHaveClass("border-dotted");
    rerender(<ClassificationBadge classification="known" />);
    expect(screen.getByRole("img")).toHaveClass("border-solid");
  });

  it("explains when the rubric capped the analyst's proposal", () => {
    render(<ClassificationBadge classification="hypothesis" proposed="inferred" />);
    expect(screen.getByText(/rubric capped from INFERRED/)).toBeInTheDocument();
  });

  it("says nothing about capping when proposal and result agree", () => {
    render(<ClassificationBadge classification="known" proposed="known" />);
    expect(screen.queryByText(/rubric capped/)).not.toBeInTheDocument();
  });
});
