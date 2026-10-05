import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { awaitingDecisionFixture as detail } from "@/test/fixtures";
import type { ReviewResponseBody } from "@/lib/types";
import { DecisionForm } from "../reviews/DecisionForm";

const review = detail.reviews.find((r) => r.kind === "decision" && r.status === "pending")!;
const unknown = detail.claims.find((c) => c.classification === "unknown")!;

function setup(canAct = true) {
  const onSubmit = vi.fn<(body: ReviewResponseBody) => Promise<void>>().mockResolvedValue();
  render(<DecisionForm review={review} claims={detail.claims} options={detail.options} canAct={canAct} onSubmit={onSubmit} />);
  return { onSubmit, user: userEvent.setup() };
}

async function fillRequired(user: ReturnType<typeof userEvent.setup>) {
  await user.selectOptions(screen.getByLabelText("Decision type"), "adopt_option");
  await user.type(screen.getByLabelText("Decision statement"), "Refresh DTS content before redesign");
  await user.type(screen.getByLabelText("Rationale"), "Strongest evidence; reversible.");
  await user.click(screen.getByRole("checkbox", { name: /Refresh the offer's content/ }));
}

describe("DecisionForm", () => {
  it("keeps submit disabled until every unknown and the uncertainties are acknowledged", async () => {
    const { user } = setup();
    const submit = screen.getByRole("button", { name: "Record decision" });
    expect(submit).toBeDisabled();

    await fillRequired(user);
    expect(submit).toBeDisabled();
    expect(screen.getByText(/Acknowledge each unresolved unknown \(1 outstanding\)/)).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox", { name: new RegExp(unknown.statement.slice(0, 40).replace(/[()']/g, ".")) }));
    expect(submit).toBeDisabled();

    await user.click(screen.getByRole("checkbox", { name: /I acknowledge the stated uncertainties/ }));
    expect(submit).toBeEnabled();

    // Un-ticking an unknown disables it again.
    await user.click(screen.getByRole("checkbox", { name: new RegExp(unknown.statement.slice(0, 40).replace(/[()']/g, ".")) }));
    expect(submit).toBeDisabled();
  });

  it("submits a decide payload in the ReviewResponseIn shape", async () => {
    const { user, onSubmit } = setup();
    await fillRequired(user);
    await user.type(screen.getByLabelText(/Conditions/), "Revisit after survey{enter}  {enter}Budget cap £50k");
    await user.click(screen.getByRole("checkbox", { name: /UNKNOWN/ }));
    await user.click(screen.getByRole("checkbox", { name: /I acknowledge the stated uncertainties/ }));
    await user.click(screen.getByRole("button", { name: "Record decision" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toEqual({
      action: "decide",
      note: null,
      challenges: [],
      classification_overrides: [],
      research_requests: [],
      additional_iterations: 0,
      decision: {
        decision_type: "adopt_option",
        statement: "Refresh DTS content before redesign",
        rationale: "Strongest evidence; reversible.",
        option_ids: ["opt_1924dfc318"],
        conditions: ["Revisit after survey", "Budget cap £50k"],
        uncertainties_acknowledged: true,
        acknowledged_unknown_claim_ids: [unknown.id],
      },
    });
  });

  it("requires an option when adopting one", async () => {
    const { user } = setup();
    await user.selectOptions(screen.getByLabelText("Decision type"), "adopt_option");
    expect(screen.getByText("Select the option(s) being adopted.")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Decision type"), "defer");
    expect(screen.queryByText("Select the option(s) being adopted.")).not.toBeInTheDocument();
  });

  it("includes optional reviewer inputs (override, challenge, iterations)", async () => {
    const { user, onSubmit } = setup();
    await user.selectOptions(screen.getByLabelText("Decision type"), "commission_further_investigation");
    await user.type(screen.getByLabelText("Decision statement"), "Commission a destination survey");
    await user.type(screen.getByLabelText("Rationale"), "Destination is unknown");
    await user.click(screen.getByRole("checkbox", { name: /UNKNOWN/ }));
    await user.click(screen.getByRole("checkbox", { name: /I acknowledge the stated uncertainties/ }));

    const claim = detail.claims.find((c) => c.classification === "inferred")!;
    await user.click(screen.getByText(/Challenge, request research, override/));
    await user.selectOptions(screen.getAllByLabelText("Claim")[0], claim.id);
    await user.selectOptions(screen.getByLabelText("New classification"), "hypothesis");
    // Incomplete override blocks submission.
    expect(screen.getByRole("button", { name: "Record decision" })).toBeDisabled();
    await user.type(screen.getByLabelText("Reason (recorded)"), "Only anecdotal support");
    await user.selectOptions(screen.getByLabelText("Target"), "investigation");
    await user.type(screen.getByLabelText("Argument"), "Volume may be the wrong measure");
    await user.clear(screen.getByLabelText(/Additional research iterations/));
    await user.type(screen.getByLabelText(/Additional research iterations/), "2");
    await user.click(screen.getByRole("button", { name: "Record decision" }));

    const body = onSubmit.mock.calls[0][0];
    expect(body.classification_overrides).toEqual([
      { claim_id: claim.id, classification: "hypothesis", reason: "Only anecdotal support" },
    ]);
    expect(body.challenges).toEqual([{ target_id: "investigation", argument: "Volume may be the wrong measure" }]);
    expect(body.additional_iterations).toBe(2);
  });

  it("disables everything for a persona without the decision_maker role", () => {
    setup(false);
    expect(screen.getByLabelText("Decision type")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Record decision" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Request further investigation/ })).toBeDisabled();
  });

  it("can request further investigation without recording a decision", async () => {
    const { user, onSubmit } = setup();
    await user.click(screen.getByRole("button", { name: /Request further investigation/ }));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ action: "request_further_investigation" });
    expect(onSubmit.mock.calls[0][0].decision).toBeUndefined();
  });
});
