"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime, humanise } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { ErrorNotice } from "../../ErrorNotice";
import { Button } from "../../ui/Button";
import { EmptyState, Mono, SectionHeading } from "../../ui/Panel";
import { ActorKindBadge } from "../../ui/StatusBadges";
import { useWorkspace } from "../WorkspaceContext";

type ActorFilter = "all" | "human" | "agent" | "system";

export function AuditTrail() {
  const { detail, persona } = useWorkspace();
  const audit = useAsync(() => api.getAudit(detail.summary.id), [detail.summary.id, detail.audit_count, persona.key]);
  const [actor, setActor] = useState<ActorFilter>("all");
  const [policyOnly, setPolicyOnly] = useState(false);
  const [newestFirst, setNewestFirst] = useState(false);

  const rows = (audit.data ?? [])
    .filter((e) => actor === "all" || e.actor_kind === actor)
    .filter((e) => !policyOnly || e.policy_rule_id)
    .sort((a, b) => (newestFirst ? b.at.localeCompare(a.at) : a.at.localeCompare(b.at)));

  return (
    <div>
      <SectionHeading
        title="Audit trail"
        description="Append-only record of what every human, agent and system component did, with the governing policy rule where one applied."
      />
      <div className="mb-3 flex flex-wrap items-center gap-3 text-[13px]">
        <div role="radiogroup" aria-label="Actor kind" className="flex gap-1">
          {(["all", "human", "agent", "system"] as const).map((k) => (
            <label
              key={k}
              className={`cursor-pointer rounded border px-2 py-0.5 text-xs ${actor === k ? "border-accent bg-accent-soft font-semibold text-accent" : "border-line-strong"}`}
            >
              <input type="radio" className="sr-only" name="actor" checked={actor === k} onChange={() => setActor(k)} />
              {humanise(k)}
            </label>
          ))}
        </div>
        <label className="flex items-center gap-1.5 text-xs">
          <input type="checkbox" checked={policyOnly} onChange={(e) => setPolicyOnly(e.target.checked)} />
          Policy-governed events only
        </label>
        <Button variant="ghost" onClick={() => setNewestFirst((v) => !v)}>
          {newestFirst ? "Newest first" : "Oldest first"} ⇅
        </Button>
        <span className="ml-auto text-xs text-ink-muted">
          {rows.length} shown · {audit.data?.length ?? 0} loaded · {detail.audit_count} recorded
        </span>
      </div>
      {audit.error && <ErrorNotice error={audit.error} context="Could not load the audit trail" />}
      {audit.loading && !audit.data && <p className="text-[13px] text-ink-muted">Loading audit trail…</p>}
      {audit.data && rows.length === 0 && <EmptyState>No events match.</EmptyState>}
      {rows.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full min-w-[860px] text-left text-[13px]">
            <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-1.5 font-medium">Time (UTC)</th>
                <th className="px-3 py-1.5 font-medium">Actor</th>
                <th className="px-3 py-1.5 font-medium">Action</th>
                <th className="px-3 py-1.5 font-medium">Policy rule</th>
                <th className="px-3 py-1.5 font-medium">Summary</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className={`border-b border-line align-top last:border-0 ${e.actor_kind === "human" ? "bg-accent-soft/40" : ""}`}>
                  <td className="whitespace-nowrap px-3 py-1.5 font-mono text-[11.5px] text-ink-muted">{formatDateTime(e.at).replace(" UTC", "")}</td>
                  <td className="px-3 py-1.5">
                    <div className="flex flex-col items-start gap-0.5">
                      <ActorKindBadge kind={e.actor_kind} />
                      <span className="font-mono text-[11px] text-ink-subtle">{e.actor_id}</span>
                    </div>
                  </td>
                  <td className="px-3 py-1.5">
                    <span className="font-medium">{humanise(e.action)}</span>
                    {e.subject_id && (
                      <p className="text-[11px] text-ink-subtle">
                        {e.subject_type} <Mono>{e.subject_id}</Mono>
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-1.5">{e.policy_rule_id ? <Mono>{e.policy_rule_id}</Mono> : <span className="text-ink-subtle">—</span>}</td>
                  <td className="px-3 py-1.5">{e.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
