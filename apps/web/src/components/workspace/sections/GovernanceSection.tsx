"use client";

import { TEAM_MODE } from "@/lib/roles";

import { EmptyState, SectionHeading } from "../../ui/Panel";
import { ReviewHistory } from "../reviews/ReviewHistory";
import { ReviewPanel } from "../reviews/ReviewPanel";
import { useWorkspace } from "../WorkspaceContext";

export function GovernanceSection() {
  const { detail } = useWorkspace();
  const pending = detail.reviews.filter((r) => r.status === "pending");
  return (
    <div className="space-y-8">
      <div>
        <SectionHeading
          title="Governance & reviews"
          description={
            TEAM_MODE
              ? "Policy gates pause the graph for a human with the required role: privacy release, findings with open blocking challenges, high-consequence options, and the decision itself. Every response is attributed and audited."
              : "The agents work autonomously until policy requires your approval: releasing confidential documents, accepting findings while challenges remain open, presenting high-consequence options, and the decision itself. Every response is recorded in the audit trail."
          }
        />
        {pending.length === 0 ? (
          <EmptyState>No review is waiting. The graph is {detail.summary.status.replace(/_/g, " ")}.</EmptyState>
        ) : (
          <div className="space-y-4">
            {pending.map((r) => (
              <ReviewPanel key={r.id} review={r} />
            ))}
          </div>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-[14px] font-semibold">Resolved reviews</h3>
        <ReviewHistory reviews={detail.reviews} />
      </div>
    </div>
  );
}
