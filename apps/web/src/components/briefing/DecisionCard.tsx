"use client";

import { useState } from "react";
import { RESEARCH_FIRST, decisionOptions, rankOptions, simpleDecisionPayload } from "@/lib/briefing";
import { formatDateTime } from "@/lib/format";
import { parseDecisionContext } from "@/lib/review-context";
import type { HumanReview } from "@/lib/types";
import { Button } from "../ui/Button";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useRespond } from "./useRespond";

export function DecisionCard({ review }: { review: HumanReview | undefined }) {
  const { detail } = useWorkspace();
  if (detail.decision) {
    const d = detail.decision;
    return (
      <section id="decision" className="rounded-lg border border-line bg-surface p-5">
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-subtle">Your decision</p>
        <p className="mt-1 text-lg font-semibold text-ink">{d.statement}</p>
        {d.rationale && <p className="mt-1 text-[15px] text-ink-muted">{d.rationale}</p>}
        <p className="mt-2 text-sm text-ink-subtle">
          Recorded by {d.decided_by.display_name} · {formatDateTime(d.decided_at)}
        </p>
      </section>
    );
  }
  if (!review) return null;
  return <DecisionForm review={review} />;
}

function DecisionForm({ review }: { review: HumanReview }) {
  const { detail, reload } = useWorkspace();
  const options = rankOptions(decisionOptions(detail, review));
  const [showAll, setShowAll] = useState(false);
  const unknownIds = parseDecisionContext(review.context).unknowns.map((u) => u.id);
  const [choice, setChoice] = useState<string>("");
  const [why, setWhy] = useState("");
  const [understood, setUnderstood] = useState(false);
  const { busy, error, submit } = useRespond(detail.summary.id, review.id, reload);
  const ready = choice !== "" && why.trim().length > 0 && (understood || unknownIds.length === 0) && !busy;

  return (
    <section id="decision" className="rounded-lg border-2 border-ink/20 bg-surface p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-ink-subtle">Your decision</p>
      <h2 className="mt-1 text-lg font-semibold text-ink">What will you do?</h2>
      <p className="mt-1 text-sm text-ink-muted">The options above are the agents’ suggestions. Only you can decide.</p>
      <div className="mt-4 space-y-2">
        {(showAll ? options : options.slice(0, 4)).map((o) => (
          <label key={o.id} className="flex items-start gap-3 rounded border border-line p-3 hover:bg-surface-muted">
            <input type="radio" name="choice" className="mt-1" checked={choice === o.id} onChange={() => setChoice(o.id)} />
            <span className="text-[15px] text-ink">{o.title}</span>
          </label>
        ))}
        {options.length > 4 && (
          <button type="button" className="text-sm text-accent hover:underline" onClick={() => setShowAll(!showAll)}>
            {showAll ? "Show fewer options" : `Show all ${options.length} options`}
          </button>
        )}
        <label className="flex items-start gap-3 rounded border border-line p-3 hover:bg-surface-muted">
          <input type="radio" name="choice" className="mt-1" checked={choice === RESEARCH_FIRST}
            onChange={() => setChoice(RESEARCH_FIRST)} />
          <span className="text-[15px] text-ink">Not yet — research the unknowns first</span>
        </label>
      </div>
      <label className="mt-4 block text-sm font-medium text-ink">
        Why?
        <textarea className="mt-1 w-full rounded border border-line-strong bg-surface p-2 text-sm font-normal" rows={2}
          value={why} onChange={(e) => setWhy(e.target.value)} placeholder="A sentence is enough — it goes in the audit trail." />
      </label>
      {unknownIds.length > 0 && (
        <label className="mt-3 flex items-start gap-3 text-sm text-ink">
          <input type="checkbox" className="mt-0.5 h-4 w-4" checked={understood} onChange={(e) => setUnderstood(e.target.checked)} />
          I’ve read what is still unknown and I’m deciding with that uncertainty.
        </label>
      )}
      <div className="mt-4">
        <Button variant="primary" disabled={!ready}
          onClick={() => submit({
            action: "decide",
            decision: simpleDecisionPayload(choice, why, options.find((o) => o.id === choice), unknownIds),
          })}>
          {busy ? "Recording…" : "Record my decision"}
        </Button>
      </div>
      {error && <p className="mt-2 text-sm text-danger-fg">{error}</p>}
    </section>
  );
}
