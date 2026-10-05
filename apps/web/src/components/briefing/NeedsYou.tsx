"use client";

import { useState } from "react";
import { parseClarificationContext, parseFindingsContext, parsePrivacyContext } from "@/lib/review-context";
import type { HumanReview } from "@/lib/types";
import { Button } from "../ui/Button";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useRespond } from "./useRespond";

/** The one thing the agents are waiting for, as a short, plain form. */
export function NeedsYou({ review }: { review: HumanReview }) {
  if (review.kind === "decision") {
    return (
      <Card title="Ready for your decision">
        <p>The agents have finished. Read what they found below, then make your decision at the bottom of the page.</p>
        <div className="mt-3">
          <Button variant="primary" onClick={() => document.getElementById("decision")?.scrollIntoView({ behavior: "smooth" })}>
            Go to decision
          </Button>
        </div>
      </Card>
    );
  }
  if (review.kind === "privacy_release") return <PrivacyRelease review={review} />;
  if (review.kind === "findings") return <Findings review={review} />;
  if (review.kind === "options") return <Options review={review} />;
  return <Clarification review={review} />;
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border-2 border-warn-fg/40 bg-warn-bg/60 p-5">
      <p className="text-xs font-semibold uppercase tracking-wider text-warn-fg">Needs you</p>
      <h2 className="mt-1 text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-2 text-[15px] leading-relaxed text-ink-muted">{children}</div>
    </section>
  );
}

function Problem({ error }: { error: string | null }) {
  return error ? <p className="mt-2 text-sm text-danger-fg">{error}</p> : null;
}

function PrivacyRelease({ review }: { review: HumanReview }) {
  const { detail, reload } = useWorkspace();
  const docs = parsePrivacyContext(review.context);
  const [release, setRelease] = useState<Record<string, boolean>>(
    Object.fromEntries(docs.map((d) => [d.id, d.specialCategoryTypes.length === 0])),
  );
  const [preview, setPreview] = useState<string | null>(null);
  const { busy, error, submit } = useRespond(detail.summary.id, review.id, reload);

  const describe = (d: (typeof docs)[number]) => {
    if (d.specialCategoryTypes.length) return `Contains sensitive personal information (${d.specialCategoryTypes.join(", ")}). We recommend withholding it.`;
    if (d.lowConfidenceDetections) return "Contains names; one or more may not have been recognised. Check the preview before releasing.";
    if (d.classification.personal_data !== "none") return "Contains names and contact details, replaced with codes like PERSON_0001.";
    return "Confidential business content.";
  };

  return (
    <Card title={`Can the agents read ${docs.length === 1 ? "this document" : `these ${docs.length} documents`}?`}>
      <p>Names and contact details have already been replaced with codes. Sensitive details are removed entirely. Choose what to release.</p>
      <ul className="mt-4 space-y-3">
        {docs.map((d) => (
          <li key={d.id} className="rounded-md border border-line bg-surface p-3">
            <label className="flex items-start gap-3">
              <input type="checkbox" className="mt-1 h-4 w-4" checked={release[d.id] ?? false}
                onChange={(e) => setRelease({ ...release, [d.id]: e.target.checked })} />
              <span>
                <span className="block font-medium text-ink">{d.title}</span>
                <span className="block text-sm text-ink-muted">{describe(d)}</span>
              </span>
            </label>
            <button type="button" className="ml-7 mt-1 text-sm text-accent hover:underline"
              onClick={() => setPreview(preview === d.id ? null : d.id)}>
              {preview === d.id ? "Hide" : "See what the agents will see"}
            </button>
            {preview === d.id && (
              <pre className="ml-7 mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-surface-muted p-3 font-mono text-xs text-ink">
                {d.sanitisedPreview}
              </pre>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-4">
        <Button variant="primary" disabled={busy} onClick={() => submit({
          action: "approve",
          items: docs.map((d) => ({ item_id: d.id, action: release[d.id] ? "approve" : "reject" })),
        })}>
          {busy ? "Saving…" : "Continue"}
        </Button>
      </div>
      <Problem error={error} />
    </Card>
  );
}

function Findings({ review }: { review: HumanReview }) {
  const { detail, reload } = useWorkspace();
  const ctx = parseFindingsContext(review.context);
  const { busy, error, submit } = useRespond(detail.summary.id, review.id, reload);
  return (
    <Card title="Research stopped with open questions">
      <p>The agents’ own sceptic still has {ctx.openBlockingChallenges.length} serious objection(s):</p>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
        {ctx.openBlockingChallenges.map((c) => <li key={c.id}>{c.argument}</li>)}
      </ul>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" disabled={busy} onClick={() => submit({ action: "approve" })}>Continue, noting these caveats</Button>
        <Button disabled={busy} onClick={() => submit({ action: "request_further_investigation", additional_iterations: 1 })}>
          Research more
        </Button>
      </div>
      <Problem error={error} />
    </Card>
  );
}

function Options({ review }: { review: HumanReview }) {
  const { detail, reload } = useWorkspace();
  const { busy, error, submit } = useRespond(detail.summary.id, review.id, reload);
  return (
    <Card title="Check the options before they go forward">
      <p>
        The agents drafted {review.subject_ids.length} options, some of them high-impact. Read them below. If they look
        sensible, approve them and you’ll be asked to decide.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="primary" disabled={busy} onClick={() => submit({ action: "approve" })}>Approve options</Button>
        <Button disabled={busy} onClick={() => submit({ action: "request_further_investigation", additional_iterations: 1 })}>
          Research more first
        </Button>
      </div>
      <Problem error={error} />
    </Card>
  );
}

function Clarification({ review }: { review: HumanReview }) {
  const { detail, reload } = useWorkspace();
  const ctx = parseClarificationContext(review.context);
  const [note, setNote] = useState("");
  const { busy, error, submit } = useRespond(detail.summary.id, review.id, reload);
  return (
    <Card title="The question needs a little more detail">
      <ul className="list-disc space-y-1 pl-5 text-sm">{ctx.questions.map((q) => <li key={q}>{q}</li>)}</ul>
      <textarea className="mt-3 w-full rounded border border-line-strong bg-surface p-2 text-sm" rows={3}
        value={note} onChange={(e) => setNote(e.target.value)} placeholder="Your answer" />
      <div className="mt-3 flex gap-2">
        <Button variant="primary" disabled={busy || !note.trim()} onClick={() => submit({ action: "modify", note })}>Continue</Button>
      </div>
      <Problem error={error} />
    </Card>
  );
}
