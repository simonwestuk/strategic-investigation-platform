"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { USE_FIXTURES } from "@/lib/env";
import { formatDateTime } from "@/lib/format";
import { useAsync, useFixtureStage } from "@/lib/hooks";
import { statusLabel } from "@/lib/labels";
import type { CreateInvestigationBody } from "@/lib/types";
import { ErrorNotice } from "../ErrorNotice";
import { Button } from "../ui/Button";

/** Ask a question (or try an example), then follow your investigations. */
export function InvestigationsHome() {
  const router = useRouter();
  const stage = useFixtureStage();
  const list = useAsync(() => api.listInvestigations(), [stage]);
  const scenarios = useAsync(() => api.scenarios(), []);
  const [question, setQuestion] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function start(body: CreateInvestigationBody) {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createInvestigation(body);
      await api.startInvestigation(created.id);
      router.push(`/investigations/${created.id}`);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setBusy(false);
    }
  }

  const investigations = [...(list.data ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 pt-10 md:px-6">
      <h1 className="text-2xl font-semibold text-ink">What do you want to investigate?</h1>
      <p className="mt-2 text-[15px] text-ink-muted">
        Ask a strategic question. The agents research it, test competing explanations, and come back to you for the
        decisions.
      </p>

      <form className="mt-5" onSubmit={(e) => { e.preventDefault(); void start({ question: question.trim(), organisation: organisation.trim() || null }); }}>
        <textarea className="w-full rounded-lg border border-line-strong bg-surface p-3 text-[15px]" rows={3}
          value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Why has customer churn increased this year, and what should we do about it?" />
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <input className="min-w-0 flex-1 rounded border border-line-strong bg-surface px-3 py-2 text-sm"
            value={organisation} onChange={(e) => setOrganisation(e.target.value)} placeholder="Organisation (optional)" />
          <Button variant="primary" type="submit" disabled={busy || question.trim().length < 10 || USE_FIXTURES}>
            {busy ? "Starting…" : "Investigate"}
          </Button>
        </div>
      </form>

      {(scenarios.data ?? []).length > 0 && (
        <div className="mt-8">
          <p className="text-sm font-medium text-ink">Or try an example (fictional data, works without any API keys)</p>
          <div className="mt-2 grid gap-3 sm:grid-cols-2">
            {[...(scenarios.data ?? [])].sort((a, b) => (a.id === "northstar" ? -1 : b.id === "northstar" ? 1 : 0)).map((s) => (
              <button key={s.id} type="button" disabled={busy || USE_FIXTURES}
                onClick={() => void start({ scenario_id: s.id })}
                className="rounded-lg border border-line bg-surface p-4 text-left hover:border-accent disabled:opacity-60">
                <span className="block text-[15px] font-medium text-ink">{s.organisation}</span>
                <span className="mt-1 block text-sm text-ink-muted">{s.question}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <div className="mt-4"><ErrorNotice error={error} context="Could not start the investigation" /></div>}

      {investigations.length > 0 && (
        <div className="mt-12">
          <h2 className="text-lg font-semibold text-ink">Your investigations</h2>
          <ul className="mt-3 divide-y divide-line rounded-lg border border-line bg-surface">
            {investigations.map((inv) => (
              <li key={inv.id}>
                <Link href={`/investigations/${inv.id}`} className="block px-4 py-3 hover:bg-surface-muted">
                  <span className="block text-[15px] text-ink">{inv.question}</span>
                  <span className="mt-0.5 block text-sm text-ink-subtle">
                    {inv.status === "awaiting_review" || inv.status === "awaiting_decision" ? (
                      <span className="font-medium text-warn-fg">Waiting for you</span>
                    ) : statusLabel(inv.status)}
                    {" · "}{formatDateTime(inv.updated_at)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
      {list.error && <div className="mt-4"><ErrorNotice error={list.error} context="Could not load investigations" /></div>}
    </div>
  );
}
