"use client";

import { api } from "@/lib/api";
import { formatDateTime, humanise } from "@/lib/format";
import { hasRole } from "@/lib/roles";
import type { HumanReview, ReviewResponseBody } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { Mono, Panel } from "../../ui/Panel";
import { useWorkspace } from "../WorkspaceContext";
import { ClarificationForm } from "./ClarificationForm";
import { DecisionForm } from "./DecisionForm";
import { FindingsReviewForm } from "./FindingsReviewForm";
import { OptionsReviewForm } from "./OptionsReviewForm";
import { PrivacyReleaseForm } from "./PrivacyReleaseForm";
import { RoleGate } from "./RoleGate";

/** A pending human review with the purpose-built form for its kind. */
export function ReviewPanel({ review }: { review: HumanReview }) {
  const { detail, persona, reload } = useWorkspace();
  const canAct = hasRole(persona.roles, review.required_role);

  async function onSubmit(body: ReviewResponseBody) {
    await api.respondToReview(detail.summary.id, review.id, body);
    reload();
  }

  const props = { review, claims: detail.claims, canAct, onSubmit };

  return (
    <Panel
      title={
        <span className="flex flex-wrap items-center gap-2">
          <Badge tone="warn">Pending · {humanise(review.kind)}</Badge>
          {review.title}
        </span>
      }
      subtitle={
        <>
          Requested {formatDateTime(review.requested_at)} · policy {review.policy_rule_ids.map((p) => <Mono key={p}>{p} </Mono>)}
        </>
      }
      className="border-warn-fg/40"
    >
      <div className="space-y-3">
        <p className="text-[13px] text-ink">{review.reason}</p>
        <RoleGate required={review.required_role} persona={persona} />
        {review.kind === "privacy_release" && <PrivacyReleaseForm {...props} />}
        {review.kind === "findings" && <FindingsReviewForm {...props} />}
        {review.kind === "options" && <OptionsReviewForm {...props} options={detail.options} />}
        {review.kind === "decision" && <DecisionForm {...props} options={detail.options} />}
        {review.kind === "clarification" && <ClarificationForm {...props} />}
      </div>
    </Panel>
  );
}
