"use client";

import { useState } from "react";
import { humanise } from "@/lib/format";
import { parsePrivacyContext } from "@/lib/review-context";
import { type CommonReviewState, EMPTY_COMMON, buildResponse, commonProblems } from "@/lib/reviews";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Mono } from "../../ui/Panel";
import { ClassificationTags, EntityTable } from "../ScanSummary";
import { CommonReviewFields } from "./CommonReviewFields";
import { FormFooter, Problems } from "./FormFooter";
import type { ReviewFormProps } from "./types";
import { useSubmit } from "./useSubmit";

type ItemChoice = "approve" | "reject" | "";

/** Per-document release decision for content the privacy gateway could not release automatically. */
export function PrivacyReleaseForm({ review, claims, canAct, onSubmit }: ReviewFormProps) {
  const docs = parsePrivacyContext(review.context);
  const [choices, setChoices] = useState<Record<string, ItemChoice>>({});
  const [common, setCommon] = useState<CommonReviewState>(EMPTY_COMMON);
  const { busy, error, run } = useSubmit(onSubmit);

  const undecided = docs.filter((d) => !choices[d.id]).length;
  const problems = [
    ...(undecided > 0 ? [`Approve or reject each document (${undecided} undecided).`] : []),
    ...commonProblems(common),
  ];
  const allRejected = docs.length > 0 && docs.every((d) => choices[d.id] === "reject");

  function submit() {
    const items = docs.map((d) => ({ item_id: d.id, action: choices[d.id] as "approve" | "reject" }));
    void run(buildResponse(allRejected ? "reject" : "approve", common, { items }));
  }

  return (
    <form
      aria-label="Privacy release review"
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (problems.length === 0) submit();
      }}
    >
      <fieldset disabled={!canAct || busy} className="space-y-3">
        {docs.map((d) => (
          <article key={d.id} className="rounded-md border border-line bg-surface" aria-labelledby={`doc-${d.id}`}>
            <header className="flex flex-wrap items-start justify-between gap-2 border-b border-line px-3 py-2">
              <div className="min-w-0">
                <h4 id={`doc-${d.id}`} className="text-[13px] font-semibold">
                  {d.title}
                </h4>
                <p className="text-xs text-ink-subtle">
                  <Mono>{d.filename}</Mono> · {humanise(d.kind)} · <Mono>{d.id}</Mono>
                </p>
              </div>
              <div role="radiogroup" aria-label={`Release decision for ${d.title}`} className="flex gap-1.5">
                {(["approve", "reject"] as const).map((a) => (
                  <label
                    key={a}
                    className={`flex cursor-pointer items-center gap-1.5 rounded border px-2.5 py-1 text-[13px] ${
                      choices[d.id] === a
                        ? a === "approve"
                          ? "border-ok-fg bg-ok-bg text-ok-fg"
                          : "border-danger-fg bg-danger-bg text-danger-fg"
                        : "border-line-strong"
                    }`}
                  >
                    <input
                      type="radio"
                      name={`release-${d.id}`}
                      value={a}
                      checked={choices[d.id] === a}
                      onChange={() => setChoices((c) => ({ ...c, [d.id]: a }))}
                    />
                    {a === "approve" ? "Release sanitised version" : "Withhold"}
                  </label>
                ))}
              </div>
            </header>
            <div className="grid gap-4 p-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
              <div className="space-y-2 text-[13px]">
                <ClassificationTags c={d.classification} />
                <EntityTable counts={d.entityCounts} />
                <div className="flex flex-wrap gap-1.5">
                  {d.lowConfidenceDetections > 0 && (
                    <Badge tone="warn">⚠ {d.lowConfidenceDetections} low-confidence detection(s)</Badge>
                  )}
                  {d.specialCategoryTypes.map((t) => (
                    <Badge key={t} tone="danger">
                      Special category: {humanise(t)}
                    </Badge>
                  ))}
                  {d.confidentialityMarkers.map((m) => (
                    <Badge key={m} tone="muted">
                      Marker: {m}
                    </Badge>
                  ))}
                </div>
                <p className="rounded bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted">
                  Policy <Mono>{d.policyRule}</Mono>: {d.policyReason}
                </p>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-ink-muted">Sanitised preview (what agents would see)</p>
                <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded border border-line bg-surface-muted p-2.5 font-mono text-[11.5px] leading-relaxed">
                  {d.sanitisedPreview}
                </pre>
              </div>
            </div>
          </article>
        ))}
        <CommonReviewFields value={common} onChange={setCommon} claims={claims} idPrefix={`priv-${review.id}`} />
      </fieldset>
      <FormFooter error={error}>
        <Button type="submit" variant="primary" disabled={!canAct || busy || problems.length > 0}>
          {busy ? "Submitting…" : "Submit release decisions"}
        </Button>
        <Button
          variant="secondary"
          disabled={!canAct || busy}
          onClick={() => setChoices(Object.fromEntries(docs.map((d) => [d.id, "approve" as const])))}
        >
          Mark all for release
        </Button>
      </FormFooter>
      {canAct && <Problems items={problems} />}
    </form>
  );
}
