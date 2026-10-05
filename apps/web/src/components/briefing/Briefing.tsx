"use client";

import clsx from "clsx";
import Link from "next/link";
import { useMemo, useState } from "react";
import { type BriefingItem, type StepState, buildBriefing, progress, rankOptions } from "@/lib/briefing";
import { api } from "@/lib/api";
import { formatCost } from "@/lib/format";
import type { StrategicOption } from "@/lib/types";
import { Button } from "../ui/Button";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { DecisionCard } from "./DecisionCard";
import { NeedsYou } from "./NeedsYou";

/** The single-operator view: a short briefing, with all detail one click away. */
export function Briefing() {
  const { detail, reload } = useWorkspace();
  const briefing = useMemo(() => buildBriefing(detail), [detail]);
  const { steps, line } = progress(detail);
  const pending = detail.reviews.find((r) => r.id === detail.pending_review_id && r.status === "pending");
  const decisionReview = pending?.kind === "decision" ? pending : undefined;
  const hasResults = briefing.found.length + briefing.ruledOut.length > 0;
  const options = rankOptions(detail.options.filter((o) => o.review_status !== "rejected"));
  const [starting, setStarting] = useState(false);

  return (
    <div className="mx-auto max-w-3xl px-4 pb-24 pt-6 md:px-6">
      <Link href="/" className="text-sm text-ink-muted hover:text-ink">← All investigations</Link>
      <h1 className="mt-3 text-2xl font-semibold leading-snug text-ink">{detail.summary.question}</h1>
      <p className="mt-2 text-[15px] text-ink-muted">
        {line}
        {detail.usage && detail.usage.searches > 0 && (
          <span className="text-ink-subtle"> · {detail.usage.searches} searches · {formatCost(detail.usage.cost_usd)}</span>
        )}
      </p>

      <ol className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-sm">
        {steps.map((s) => <Step key={s.label} label={s.label} state={s.state} />)}
      </ol>

      {detail.summary.status === "draft" && (
        <div className="mt-6">
          <Button variant="primary" disabled={starting}
            onClick={async () => { setStarting(true); await api.startInvestigation(detail.summary.id); reload(); }}>
            Start the investigation
          </Button>
        </div>
      )}
      {detail.summary.status === "failed" && (
        <p className="mt-6 rounded border border-danger-fg/40 bg-danger-bg p-3 text-sm text-danger-fg">
          The run failed: {detail.summary.error}
        </p>
      )}

      {pending && pending.kind !== "decision" && <div className="mt-6"><NeedsYou review={pending} /></div>}
      {decisionReview && <div className="mt-6"><NeedsYou review={decisionReview} /></div>}

      {!hasResults && detail.summary.status === "running" && (
        <p className="mt-8 text-[15px] text-ink-muted">
          Findings will appear here as the agents work. This page updates by itself.
        </p>
      )}

      {hasResults && (
        <>
          <Section title="What we found" hint="Likely causes, with the strongest piece of evidence for each.">
            <ShowMore items={briefing.found} first={4} noun="finding" render={(i) => <Finding key={i.id} item={i} tone="found" />} />
          </Section>
          {briefing.ruledOut.length > 0 && (
            <Section title="Ruled out" hint="Explanations the evidence does not support.">
              {briefing.ruledOut.map((i) => <Finding key={i.id} item={i} tone="ruled_out" />)}
            </Section>
          )}
          {briefing.unknown.length > 0 && (
            <Section title="Still unknown" hint="What the evidence can't tell us yet.">
              {briefing.unknown.map((u) => (
                <Row key={u.id} mark="?" markClass="border border-dashed border-unknown-line text-unknown-fg"
                  title={u.label} body={u.needs} claimId={u.claimId} />
              ))}
            </Section>
          )}
        </>
      )}

      {options.length > 0 && (
        <Section title="Options" hint="Suggested by the agents. These are recommendations, not decisions.">
          <ShowMore items={options} first={4} noun="option" render={(o) => <OptionCard key={o.id} option={o} />} />
        </Section>
      )}

      {(decisionReview || detail.decision) && <div className="mt-10"><DecisionCard review={decisionReview} /></div>}

      {detail.summary.status !== "draft" && (
        <p className="mt-12 border-t border-line pt-4 text-sm text-ink-muted">
          Want to check the working? <a href="#decision-room" className="text-accent hover:underline">
            See every source, claim, hypothesis and audit entry →</a>
        </p>
      )}
    </div>
  );
}

function ShowMore<T>({ items, first, noun, render }: {
  items: readonly T[]; first: number; noun: string; render: (item: T) => React.ReactNode;
}) {
  const [all, setAll] = useState(false);
  const shown = all ? items : items.slice(0, first);
  const hidden = items.length - first;
  return (
    <div className="space-y-3">
      {shown.map(render)}
      {hidden > 0 && (
        <button type="button" className="text-sm text-accent hover:underline" onClick={() => setAll(!all)}>
          {all ? `Show fewer ${noun}s` : `Show ${hidden} more ${noun}${hidden > 1 ? "s" : ""}`}
        </button>
      )}
    </div>
  );
}

function Step({ label, state }: { label: string; state: StepState }) {
  const mark = { done: "✓", active: "●", waiting: "!", todo: "○" }[state];
  return (
    <li className={clsx("flex items-center gap-1.5",
      state === "done" && "text-ok-fg", state === "active" && "text-accent font-medium",
      state === "waiting" && "text-warn-fg font-medium", state === "todo" && "text-ink-subtle")}>
      <span aria-hidden="true">{mark}</span>{label}
      {state === "waiting" && <span className="sr-only"> (waiting for you)</span>}
    </li>
  );
}

function Section({ title, hint, children }: { title: string; hint: string; children: React.ReactNode }) {
  return (
    <section className="mt-10">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <p className="mb-3 text-sm text-ink-subtle">{hint}</p>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function Finding({ item, tone }: { item: BriefingItem; tone: "found" | "ruled_out" }) {
  const where = item.where.length ? (tone === "found" ? `In ${item.where.join(", ")}` : `Tested in ${item.where.join(", ")}`) : null;
  return (
    <Row
      mark={tone === "found" ? "✓" : "✕"}
      markClass={tone === "found" ? "bg-ok-bg text-ok-fg" : "bg-danger-bg text-danger-fg"}
      title={item.label}
      meta={[where, item.confidence].filter(Boolean).join(" · ") || null}
      body={item.fact ? `“${item.fact}”` : null}
      claimId={item.claimId}
    />
  );
}

function Row({ mark, markClass, title, meta, body, claimId }: {
  mark: string; markClass: string; title: string; meta?: string | null; body: string | null; claimId: string | null;
}) {
  const { openClaim } = useWorkspace();
  return (
    <div className="flex gap-3">
      <span className={clsx("mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-sm", markClass)}
        aria-hidden="true">{mark}</span>
      <div className="min-w-0">
        <p className="text-[15px] font-medium text-ink">{title}</p>
        {meta && <p className="text-sm text-ink-subtle">{meta}</p>}
        {body && <p className="mt-0.5 text-sm text-ink-muted">{body}</p>}
        {claimId && (
          <button type="button" className="mt-0.5 text-sm text-accent hover:underline" onClick={() => openClaim(claimId)}>
            Evidence →
          </button>
        )}
      </div>
    </div>
  );
}

const IMPACT: Record<string, string> = { high: "Big change", medium: "Moderate change", low: "Small change" };
const REVERSE: Record<string, string> = { high: "easy to undo", medium: "partly reversible", low: "hard to undo" };

function OptionCard({ option }: { option: StrategicOption }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <p className="text-[15px] font-semibold text-ink">{option.title}</p>
      <p className="mt-1 text-sm text-ink-muted">{option.description}</p>
      <p className="mt-2 text-xs text-ink-subtle">
        {IMPACT[option.consequence] ?? option.consequence} · {REVERSE[option.reversibility] ?? option.reversibility}
        {option.finding_ids.length > 0 && ` · based on ${option.finding_ids.length} finding${option.finding_ids.length > 1 ? "s" : ""}`}
      </p>
      {(option.risks.length > 0 || option.uncertainties.length > 0) && (
        <button type="button" className="mt-2 text-sm text-accent hover:underline" onClick={() => setOpen(!open)}>
          {open ? "Hide risks" : "Risks and uncertainties"}
        </button>
      )}
      {open && (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink-muted">
          {[...option.risks, ...option.uncertainties].map((r) => <li key={r}>{r}</li>)}
        </ul>
      )}
    </div>
  );
}
