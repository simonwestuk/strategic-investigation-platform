"use client";

import { useState } from "react";
import { humanise } from "@/lib/format";
import { parseContextOptions } from "@/lib/review-context";
import { type CommonReviewState, EMPTY_COMMON, buildResponse, commonProblems, splitLines } from "@/lib/reviews";
import type { ItemDecision, StrategicOption } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { Button, inputClass, labelClass } from "../../ui/Button";
import { ConfidenceMeter } from "../../ui/ConfidenceMeter";
import { AiRecommendationLabel } from "../../ui/StatusBadges";
import { CommonReviewFields } from "./CommonReviewFields";
import { FormFooter, Problems } from "./FormFooter";
import type { ReviewFormProps } from "./types";
import { useSubmit } from "./useSubmit";

type Choice = "approve" | "modify" | "reject";

interface Edit {
  title: string;
  description: string;
  risks: string;
}

/** Governance review of AI-generated options before decision-makers see them. */
export function OptionsReviewForm({
  review,
  claims,
  canAct,
  onSubmit,
  options,
}: ReviewFormProps & { options: readonly StrategicOption[] }) {
  const ctxOptions = parseContextOptions(review.context);
  const byId = new Map(options.map((o) => [o.id, o]));
  const [choices, setChoices] = useState<Record<string, Choice>>(() =>
    Object.fromEntries(ctxOptions.map((o) => [o.id, "approve" as Choice])),
  );
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [common, setCommon] = useState<CommonReviewState>(EMPTY_COMMON);
  const { busy, error, run } = useSubmit(onSubmit);

  const editFor = (id: string): Edit => {
    const o = byId.get(id);
    return edits[id] ?? { title: o?.title ?? "", description: o?.description ?? "", risks: (o?.risks ?? []).join("\n") };
  };

  const problems = commonProblems(common);
  const ok = canAct && !busy && problems.length === 0;

  function submit() {
    const items: ItemDecision[] = ctxOptions.map((o) => ({
      item_id: o.id,
      action: choices[o.id] ?? "approve",
      note: notes[o.id]?.trim() || null,
    }));
    const optionEdits: Record<string, Record<string, unknown>> = {};
    for (const o of ctxOptions) {
      if (choices[o.id] !== "modify" || !edits[o.id]) continue;
      const orig = byId.get(o.id);
      const e = edits[o.id];
      const changed: Record<string, unknown> = {};
      if (e.title.trim() && e.title.trim() !== orig?.title) changed.title = e.title.trim();
      if (e.description.trim() && e.description.trim() !== orig?.description) changed.description = e.description.trim();
      const risks = splitLines(e.risks);
      if (JSON.stringify(risks) !== JSON.stringify(orig?.risks ?? [])) changed.risks = risks;
      if (Object.keys(changed).length) optionEdits[o.id] = changed;
    }
    const anyChange = items.some((i) => i.action !== "approve");
    void run(buildResponse(anyChange ? "modify" : "approve", common, { items, option_edits: optionEdits }));
  }

  return (
    <form aria-label="Options review" className="space-y-4" onSubmit={(e) => e.preventDefault()}>
      <fieldset disabled={!canAct || busy} className="space-y-2">
        {ctxOptions.map((o) => {
          const full = byId.get(o.id);
          const choice = choices[o.id] ?? "approve";
          const edit = editFor(o.id);
          return (
            <article key={o.id} className="rounded-md border border-dashed border-ai-line bg-surface px-3 py-2.5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <AiRecommendationLabel />
                    {full && <ConfidenceMeter band={full.confidence_band} />}
                    {o.consequence && <Badge tone={o.consequence === "high" ? "warn" : "muted"}>{humanise(o.consequence)} consequence</Badge>}
                    {full && <Badge tone="muted">{humanise(full.reversibility)} reversibility</Badge>}
                  </div>
                  <h4 className="text-[13px] font-semibold">{o.title}</h4>
                  {full && <p className="text-[13px] text-ink-muted">{full.description}</p>}
                </div>
                <div role="radiogroup" aria-label={`Review of ${o.title}`} className="flex shrink-0 gap-1">
                  {(["approve", "modify", "reject"] as const).map((a) => (
                    <label
                      key={a}
                      className={`flex cursor-pointer items-center gap-1 rounded border px-2 py-0.5 text-xs ${
                        choice === a ? "border-accent bg-accent-soft font-semibold text-accent" : "border-line-strong"
                      }`}
                    >
                      <input
                        type="radio"
                        className="sr-only"
                        name={`opt-${o.id}`}
                        checked={choice === a}
                        onChange={() => setChoices((c) => ({ ...c, [o.id]: a }))}
                      />
                      {humanise(a)}
                    </label>
                  ))}
                </div>
              </div>
              {choice === "modify" && (
                <div className="mt-2 grid gap-2 border-t border-line pt-2 md:grid-cols-2">
                  <div className="md:col-span-2">
                    <label className={labelClass} htmlFor={`t-${o.id}`}>
                      Title
                    </label>
                    <input
                      id={`t-${o.id}`}
                      className={inputClass}
                      value={edit.title}
                      onChange={(e) => setEdits((x) => ({ ...x, [o.id]: { ...edit, title: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className={labelClass} htmlFor={`d-${o.id}`}>
                      Description
                    </label>
                    <textarea
                      id={`d-${o.id}`}
                      rows={3}
                      className={inputClass}
                      value={edit.description}
                      onChange={(e) => setEdits((x) => ({ ...x, [o.id]: { ...edit, description: e.target.value } }))}
                    />
                  </div>
                  <div>
                    <label className={labelClass} htmlFor={`r-${o.id}`}>
                      Risks (one per line)
                    </label>
                    <textarea
                      id={`r-${o.id}`}
                      rows={3}
                      className={inputClass}
                      value={edit.risks}
                      onChange={(e) => setEdits((x) => ({ ...x, [o.id]: { ...edit, risks: e.target.value } }))}
                    />
                  </div>
                </div>
              )}
              {choice !== "approve" && (
                <div className="mt-2">
                  <label className={labelClass} htmlFor={`n-${o.id}`}>
                    Reviewer note for this option
                  </label>
                  <input
                    id={`n-${o.id}`}
                    className={inputClass}
                    value={notes[o.id] ?? ""}
                    onChange={(e) => setNotes((n) => ({ ...n, [o.id]: e.target.value }))}
                  />
                </div>
              )}
            </article>
          );
        })}
        <CommonReviewFields value={common} onChange={setCommon} claims={claims} idPrefix={`opt-${review.id}`} />
      </fieldset>
      <FormFooter error={error}>
        <Button variant="primary" disabled={!ok} onClick={submit}>
          {busy ? "Submitting…" : "Submit option review"}
        </Button>
        <Button
          variant="secondary"
          disabled={!ok}
          onClick={() => void run(buildResponse("request_further_investigation", common))}
        >
          Request further investigation
        </Button>
        <span className="text-xs text-ink-muted">Approved and modified options go to the decision-maker.</span>
      </FormFooter>
      {canAct && <Problems items={problems} />}
    </form>
  );
}
