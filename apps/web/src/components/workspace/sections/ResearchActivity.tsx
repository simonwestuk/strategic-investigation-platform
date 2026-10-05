"use client";

import { humanise, formatDateTime, pluralise } from "@/lib/format";
import { countByStatus, groupByIteration } from "@/lib/research";
import type { ResearchTask } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { EmptyState, Mono, SectionHeading } from "../../ui/Panel";
import { OriginBadge, TaskStatusBadge } from "../../ui/StatusBadges";
import { useWorkspace } from "../WorkspaceContext";

const METHOD_LABEL: Record<string, string> = {
  web_search: "Web search",
  internal_documents: "Internal documents",
  dataset_analysis: "Dataset analysis",
};

function TaskRow({ t }: { t: ResearchTask }) {
  const blocked = t.status === "blocked_unavailable";
  return (
    <tr className={`border-b border-line align-top last:border-0 ${blocked ? "bg-warn-bg/40" : ""}`}>
      <td className="px-3 py-2">
        <TaskStatusBadge status={t.status} />
      </td>
      <td className="px-3 py-2">
        <Badge tone="muted">{METHOD_LABEL[t.method] ?? t.method}</Badge>
      </td>
      <td className="px-3 py-2">
        <OriginBadge origin={t.origin} />
      </td>
      <td className="px-3 py-2">
        <p className="text-[13px]">{t.question}</p>
        {t.result_summary && <p className="mt-0.5 text-xs text-ink-muted">Result: {t.result_summary}</p>}
        {t.status_reason && (
          <p className={`mt-0.5 text-xs ${blocked ? "font-medium text-warn-fg" : "text-ink-muted"}`}>Why: {t.status_reason}</p>
        )}
        {t.queries.length > 0 && (
          <p className="mt-0.5 text-[11px] text-ink-subtle">Queries: {t.queries.map((q) => `“${q}”`).join(", ")}</p>
        )}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-xs text-ink-muted">
        {humanise(t.priority)} / {humanise(t.expected_value)}
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-xs tabular-nums text-ink-muted">
        {t.evidence_ids.length} ev · {t.source_ids.length} src
      </td>
    </tr>
  );
}

export function ResearchActivity() {
  const { detail } = useWorkspace();
  const groups = groupByIteration(detail.tasks, detail.routing);
  return (
    <div>
      <SectionHeading
        title="Research activity"
        description="Tasks planned per iteration and the routing decision that ended each round — why the graph looped for more research or stopped."
      />
      {groups.length === 0 && <EmptyState>No research has run yet.</EmptyState>}
      <ol className="space-y-5">
        {groups.map((g) => {
          const counts = countByStatus(g.tasks);
          return (
            <li key={g.iteration}>
              <div className="mb-2 flex flex-wrap items-baseline gap-3">
                <h3 className="text-[14px] font-semibold">Iteration {g.iteration}</h3>
                <span className="text-xs text-ink-muted">
                  {pluralise(g.tasks.length, "task")} ·{" "}
                  {Object.entries(counts)
                    .map(([s, n]) => `${n} ${humanise(s).toLowerCase()}`)
                    .join(", ")}
                </span>
              </div>
              {g.tasks.length > 0 && (
                <div className="overflow-x-auto rounded-md border border-line bg-surface">
                  <table className="w-full min-w-[760px] text-left text-[13px]">
                    <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
                      <tr>
                        <th className="px-3 py-1.5 font-medium">Status</th>
                        <th className="px-3 py-1.5 font-medium">Method</th>
                        <th className="px-3 py-1.5 font-medium">Origin</th>
                        <th className="px-3 py-1.5 font-medium">Question &amp; result</th>
                        <th className="px-3 py-1.5 font-medium">Priority / value</th>
                        <th className="px-3 py-1.5 font-medium">Yield</th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.tasks.map((t) => (
                        <TaskRow key={t.id} t={t} />
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {g.routing && (
                <div
                  className={`mt-2 rounded-md border px-3 py-2 text-[13px] ${
                    g.routing.continue_research ? "border-info-fg/30 bg-info-bg" : "border-ok-fg/30 bg-ok-bg"
                  }`}
                >
                  <p className="font-semibold">
                    Routing after iteration {g.routing.iteration}:{" "}
                    {g.routing.continue_research ? "↻ continue research" : `■ stop — ${humanise(g.routing.stop_reason ?? "stopped")}`}
                  </p>
                  <p className="mt-0.5">{g.routing.rationale}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    {g.routing.open_blocking_challenges} open blocking challenge(s) · {g.routing.new_evidence_last_round} new evidence
                    item(s) last round · {formatDateTime(g.routing.at)}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>
      {detail.budget && (
        <p className="mt-4 text-xs text-ink-muted">
          Budget: <Mono>max_iterations={detail.budget.max_iterations}</Mono> <Mono>max_tasks={detail.budget.max_tasks}</Mono>{" "}
          <Mono>max_searches={detail.budget.max_searches}</Mono> <Mono>max_fetches={detail.budget.max_fetches}</Mono>{" "}
          <Mono>max_llm_calls={detail.budget.max_llm_calls}</Mono> <Mono>max_cost_usd={detail.budget.max_cost_usd}</Mono>
        </p>
      )}
    </div>
  );
}
