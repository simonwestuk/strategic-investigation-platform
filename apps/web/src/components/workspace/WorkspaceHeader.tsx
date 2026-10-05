"use client";

import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatCost, formatDateTime, formatNumber } from "@/lib/format";
import { ROLE_LABELS, TEAM_MODE, hasRole } from "@/lib/roles";
import { ErrorNotice } from "../ErrorNotice";
import { Button } from "../ui/Button";
import { RunStatusBadge } from "../ui/StatusBadges";
import { useWorkspace } from "./WorkspaceContext";

function Metric({ label, value, max }: { label: string; value: string | number; max?: number }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] uppercase tracking-wider text-ink-subtle">{label}</dt>
      <dd className="font-medium tabular-nums text-ink">
        {typeof value === "number" ? formatNumber(value) : value}
        {max !== undefined && <span className="font-normal text-ink-subtle"> / {formatNumber(max)}</span>}
      </dd>
    </div>
  );
}

export function WorkspaceHeader() {
  const { detail, persona, goTo, reload } = useWorkspace();
  const { summary, frame, usage, budget } = detail;
  const pending = detail.reviews.find((r) => r.id === detail.pending_review_id) ?? detail.reviews.find((r) => r.status === "pending");
  const [startError, setStartError] = useState<Error | null>(null);
  const [starting, setStarting] = useState(false);
  const canStart = hasRole(persona.roles, "investigator");

  async function start() {
    setStarting(true);
    setStartError(null);
    try {
      await api.startInvestigation(summary.id);
      reload();
    } catch (e) {
      setStartError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setStarting(false);
    }
  }

  const tokens = (usage?.input_tokens ?? 0) + (usage?.output_tokens ?? 0);

  return (
    <div className="border-b border-line bg-surface">
      <div className="mx-auto max-w-[1440px] px-4 py-4 md:px-6">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
          <Link href="/" className="hover:underline">
            Investigations
          </Link>
          <span aria-hidden="true">/</span>
          <span className="font-mono">{summary.id}</span>
          <RunStatusBadge status={summary.status} />
          {summary.status === "running" && <span>Research in progress — refreshing every 2 seconds.</span>}
        </div>
        <h1 className="max-w-5xl text-lg font-semibold leading-snug text-ink">{summary.question}</h1>
        {frame && (
          <details className="mt-1 max-w-5xl text-[13px] text-ink-muted">
            <summary className="inline-flex items-center gap-1 text-accent">
              <span className="chevron" aria-hidden="true">
                ›
              </span>
              Scope &amp; framing
            </summary>
            <div className="mt-2 grid gap-3 rounded border border-line bg-surface-muted p-3 md:grid-cols-2">
              <div>
                <p className="text-ink">{frame.scope}</p>
                <p className="mt-2">{frame.decision_context}</p>
              </div>
              <div className="space-y-2">
                {frame.out_of_scope.length > 0 && (
                  <p>
                    <span className="font-medium text-ink">Out of scope: </span>
                    {frame.out_of_scope.join(" ")}
                  </p>
                )}
                {frame.assumptions.length > 0 && (
                  <p>
                    <span className="font-medium text-ink">Assumptions: </span>
                    {frame.assumptions.join(" ")}
                  </p>
                )}
                {frame.ambiguities.length > 0 && (
                  <p>
                    <span className="font-medium text-ink">Ambiguities: </span>
                    {frame.ambiguities.join(" ")}
                  </p>
                )}
                <p>
                  <span className="font-medium text-ink">Question type: </span>
                  {frame.question_types.join(", ")}
                </p>
              </div>
            </div>
          </details>
        )}

        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-[13px] sm:grid-cols-4 lg:grid-cols-9">
          <Metric label="Organisation" value={summary.organisation ?? "—"} />
          <Metric label="Iteration" value={detail.iteration} max={budget?.max_iterations} />
          <Metric label="Searches" value={usage?.searches ?? 0} max={budget?.max_searches} />
          <Metric label="Fetches" value={usage?.fetches ?? 0} max={budget?.max_fetches} />
          <Metric label="Model calls" value={usage?.llm_calls ?? 0} max={budget?.max_llm_calls} />
          <Metric label="Tokens" value={tokens} />
          <Metric label="Cost" value={formatCost(usage?.cost_usd ?? 0)} />
          <Metric label="Reasoner · as of" value={`${summary.reasoner} · ${summary.as_of}`} />
          <Metric label="Last activity" value={formatDateTime(summary.updated_at)} />
        </dl>

        {summary.status === "draft" && (
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <Button variant="primary" onClick={start} disabled={!canStart || starting}>
              {starting ? "Starting…" : "Start investigation"}
            </Button>
            {!canStart && <span className="text-xs text-ink-muted">Starting requires the Investigator role.</span>}
          </div>
        )}
        {startError && (
          <div className="mt-2">
            <ErrorNotice error={startError} />
          </div>
        )}
        {summary.error && (
          <div className="mt-3">
            <ErrorNotice error={new Error(summary.error)} context="Investigation failed" />
          </div>
        )}

        {pending && pending.status === "pending" && (
          <div
            role="status"
            className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded border border-warn-fg/40 bg-warn-bg px-3 py-2 text-[13px] text-warn-fg"
          >
            <div>
              <strong className="font-semibold">Waiting for you:</strong> {pending.title}.
              {TEAM_MODE && (
                <>
                  {" "}Requires <strong>{ROLE_LABELS[pending.required_role]}</strong>
                  {hasRole(persona.roles, pending.required_role)
                    ? " — you can act on this."
                    : ` — you are acting as ${persona.label}, so you can view but not respond.`}
                </>
              )}
            </div>
            <Button variant="secondary" onClick={() => goTo(pending.kind === "decision" ? "decision-room" : "governance")}>
              Open review
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
