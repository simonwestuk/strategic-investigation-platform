"use client";

import { formatDateTime } from "@/lib/format";
import { DECISION_TYPE_LABELS, statusLabel } from "@/lib/labels";
import { Badge } from "../../ui/Badge";
import { BulletList, Eyebrow, KeyValues, Panel } from "../../ui/Panel";
import { HumanDecisionLabel } from "../../ui/StatusBadges";
import { ReviewPanel } from "../reviews/ReviewPanel";
import { useWorkspace } from "../WorkspaceContext";

export function HumanDecisionPanel() {
  const { detail, lookups } = useWorkspace();
  const decision = detail.decision;
  const pending = detail.reviews.find((r) => r.kind === "decision" && r.status === "pending");

  if (decision) {
    const unknowns = decision.acknowledged_unknown_claim_ids.map((id) => lookups.claims.get(id)?.statement ?? id);
    return (
      <section aria-labelledby="decision-heading" className="rounded-md border-2 border-ink bg-surface">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h3 id="decision-heading" className="flex items-center gap-2 text-[13px] font-semibold">
            <HumanDecisionLabel /> Decision recorded
          </h3>
          <span className="text-xs text-ink-muted">
            by <strong className="text-ink">{decision.decided_by.display_name}</strong> ({decision.decided_by.id}) ·{" "}
            {formatDateTime(decision.decided_at)}
          </span>
        </header>
        <div className="space-y-3 p-4">
          <p className="text-[15px] font-semibold leading-snug">{decision.statement}</p>
          <KeyValues
            rows={[
              ["Decision type", DECISION_TYPE_LABELS[decision.decision_type]],
              ["Rationale", decision.rationale],
              [
                "Options referenced",
                decision.option_ids.length
                  ? decision.option_ids.map((id) => lookups.options.get(id)?.title ?? id).join("; ")
                  : "None",
              ],
              ["Conditions", decision.conditions.length ? <BulletList items={decision.conditions} /> : "None"],
              [
                "Uncertainties",
                decision.uncertainties_acknowledged ? (
                  <Badge tone="ok">✓ Acknowledged by the decision-maker</Badge>
                ) : (
                  <Badge tone="danger">Not acknowledged</Badge>
                ),
              ],
              ["Unknowns acknowledged", unknowns.length ? <BulletList items={unknowns} /> : "None"],
              ["Decided by roles", decision.decided_by.roles.join(", ")],
              ["Review", decision.review_id],
            ]}
          />
          <p className="text-xs text-ink-muted">
            The platform recorded this decision; it did not make it. The decision-maker&apos;s identity comes from authentication,
            never from the request body.
          </p>
        </div>
      </section>
    );
  }

  if (pending) {
    return (
      <div>
        <Eyebrow className="mb-2">Human decision</Eyebrow>
        <ReviewPanel review={pending} />
      </div>
    );
  }

  return (
    <Panel title="Human decision">
      <p className="text-[13px] text-ink-muted">
        No decision has been requested yet. Status: <strong>{statusLabel(detail.summary.status)}</strong>. A decision form appears
        here once options have passed governance review.
      </p>
    </Panel>
  );
}
