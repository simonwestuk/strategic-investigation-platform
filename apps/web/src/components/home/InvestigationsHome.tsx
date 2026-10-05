"use client";

import Link from "next/link";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useAsync, useFixtureStage, usePersona } from "@/lib/hooks";
import { ErrorNotice } from "../ErrorNotice";
import { EmptyState, Panel } from "../ui/Panel";
import { RunStatusBadge } from "../ui/StatusBadges";
import { NewInvestigationForm } from "./NewInvestigationForm";

export function InvestigationsHome() {
  const persona = usePersona();
  const stage = useFixtureStage();
  const list = useAsync(() => api.listInvestigations(), [persona.key, stage]);
  const scenarios = useAsync(() => api.scenarios(), [persona.key]);

  return (
    <div className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 md:px-6 lg:grid-cols-[minmax(0,1fr)_420px]">
      <div>
        <div className="mb-4">
          <h1 className="text-xl font-semibold">Investigations</h1>
          <p className="mt-1 max-w-2xl text-[13px] text-ink-muted">
            Each investigation frames a strategic question, researches competing explanations and separates what is
            known, inferred, hypothesised and unknown. Agents recommend; accountable people decide.
          </p>
        </div>
        {list.error && <ErrorNotice error={list.error} context="Could not load investigations" />}
        {list.loading && !list.data && <p className="text-[13px] text-ink-muted">Loading…</p>}
        {list.data && list.data.length === 0 && <EmptyState>No investigations yet. Start one from a scenario.</EmptyState>}
        {list.data && list.data.length > 0 && (
          <div className="overflow-x-auto rounded-md border border-line bg-surface">
            <table className="w-full text-left text-[13px]">
              <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
                <tr>
                  <th className="px-3 py-2 font-medium">Question</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">As of</th>
                  <th className="px-3 py-2 font-medium">Last activity</th>
                </tr>
              </thead>
              <tbody>
                {[...list.data]
                  .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
                  .map((inv) => (
                    <tr key={inv.id} className="border-b border-line last:border-0 hover:bg-surface-muted">
                      <td className="px-3 py-2.5">
                        <Link href={`/investigations/${inv.id}`} className="font-medium text-accent hover:underline">
                          {inv.question}
                        </Link>
                        <div className="mt-0.5 text-xs text-ink-subtle">
                          {inv.organisation ?? "No organisation"} · {inv.id} · reasoner {inv.reasoner}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <RunStatusBadge status={inv.status} />
                      </td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-ink-muted">{inv.as_of}</td>
                      <td className="whitespace-nowrap px-3 py-2.5 text-ink-muted">{formatDateTime(inv.updated_at)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <aside>
        <Panel title="Start a new investigation" subtitle="Requires the Investigator role.">
          {scenarios.error && <ErrorNotice error={scenarios.error} context="Could not load scenarios" />}
          <NewInvestigationForm scenarios={scenarios.data ?? []} persona={persona} />
        </Panel>
      </aside>
    </div>
  );
}
