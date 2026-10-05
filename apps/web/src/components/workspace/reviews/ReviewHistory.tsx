import { DECISION_TYPE_LABELS } from "@/lib/labels";
import { formatDateTime, humanise, pluralise } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/roles";
import type { DecisionType, HumanReview } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { EmptyState, Mono } from "../../ui/Panel";

export function ReviewHistory({ reviews }: { reviews: readonly HumanReview[] }) {
  const resolved = reviews.filter((r) => r.status === "resolved");
  if (resolved.length === 0) return <EmptyState>No reviews resolved yet.</EmptyState>;
  return (
    <ol className="space-y-2">
      {resolved.map((r) => {
        const resp = r.response;
        return (
          <li key={r.id} className="rounded-md border border-line bg-surface px-4 py-3 text-[13px]">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ok">Resolved</Badge>
              <Badge tone="muted">{humanise(r.kind)}</Badge>
              <span className="font-medium">{r.title}</span>
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              Required {ROLE_LABELS[r.required_role]} · policy {r.policy_rule_ids.join(", ") || "—"} · requested{" "}
              {formatDateTime(r.requested_at)} · <Mono>{r.id}</Mono>
            </p>
            {resp && (
              <div className="mt-2 rounded bg-surface-muted px-3 py-2">
                <p>
                  <strong>{resp.actor.display_name}</strong> <span className="text-ink-muted">({resp.actor.id})</span> responded{" "}
                  <Badge tone="accent">{humanise(resp.action)}</Badge> on {formatDateTime(resp.responded_at)}
                </p>
                <ul className="mt-1 space-y-0.5 text-xs text-ink-muted">
                  {resp.note && <li>Note: {resp.note}</li>}
                  {resp.items.length > 0 && (
                    <li>
                      Item decisions: {resp.items.map((i) => `${i.item_id} → ${humanise(i.action)}`).join("; ")}
                    </li>
                  )}
                  {Object.keys(resp.option_edits).length > 0 && <li>Edited {pluralise(Object.keys(resp.option_edits).length, "option")}</li>}
                  {resp.classification_overrides.length > 0 && (
                    <li>
                      Overrides:{" "}
                      {resp.classification_overrides.map((o) => `${o.claim_id} → ${o.classification.toUpperCase()} (${o.reason})`).join("; ")}
                    </li>
                  )}
                  {resp.challenges.length > 0 && <li>Raised {pluralise(resp.challenges.length, "human challenge")}</li>}
                  {resp.research_requests.length > 0 && <li>Research requested: {resp.research_requests.join("; ")}</li>}
                  {resp.additional_iterations > 0 && <li>Granted {pluralise(resp.additional_iterations, "extra iteration")}</li>}
                  {resp.decision && (
                    <li>
                      Decision: {DECISION_TYPE_LABELS[resp.decision.decision_type as DecisionType] ?? resp.decision.decision_type} —{" "}
                      {resp.decision.statement}
                    </li>
                  )}
                </ul>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
