"use client";

import { useState } from "react";
import { humanise } from "@/lib/format";
import { parseFindingsContext } from "@/lib/review-context";
import { type CommonReviewState, EMPTY_COMMON, buildResponse, commonProblems } from "@/lib/reviews";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Eyebrow } from "../../ui/Panel";
import { CommonReviewFields } from "./CommonReviewFields";
import { FormFooter, Problems } from "./FormFooter";
import type { ReviewFormProps } from "./types";
import { useSubmit } from "./useSubmit";

/** Research stopped with blocking challenges open: accept them as limitations or send it back. */
export function FindingsReviewForm({ review, claims, canAct, onSubmit }: ReviewFormProps) {
  const ctx = parseFindingsContext(review.context);
  const [common, setCommon] = useState<CommonReviewState>(EMPTY_COMMON);
  const { busy, error, run } = useSubmit(onSubmit);
  const problems = commonProblems(common);
  const ok = canAct && !busy && problems.length === 0;

  return (
    <form aria-label="Findings review" className="space-y-4" onSubmit={(e) => e.preventDefault()}>
      {ctx.stopReason && <p className="text-[13px] text-ink-muted">Why research stopped: {ctx.stopReason}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <Eyebrow className="mb-2">Open blocking challenges ({ctx.openBlockingChallenges.length})</Eyebrow>
          <ul className="space-y-2">
            {ctx.openBlockingChallenges.map((c) => (
              <li key={c.id} className="rounded border border-danger-fg/30 px-3 py-2 text-[13px]">
                <Badge tone="danger">{humanise(c.kind)}</Badge>
                <p className="mt-1">{c.argument}</p>
                <p className="mt-0.5 font-mono text-[11px] text-ink-subtle">target {c.targetId}</p>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <Eyebrow className="mb-2">Draft findings ({ctx.findings.length})</Eyebrow>
          <ul className="max-h-80 space-y-1.5 overflow-auto">
            {ctx.findings.map((f) => (
              <li key={f.id} className="rounded border border-line px-3 py-1.5 text-[13px]">
                {f.statement}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <fieldset disabled={!canAct || busy}>
        <CommonReviewFields value={common} onChange={setCommon} claims={claims} idPrefix={`fnd-${review.id}`} />
      </fieldset>
      <FormFooter error={error}>
        <Button variant="primary" disabled={!ok} onClick={() => void run(buildResponse("approve", common))}>
          Accept findings (open challenges become stated limitations)
        </Button>
        <Button variant="secondary" disabled={!ok} onClick={() => void run(buildResponse("request_further_investigation", common))}>
          Request further investigation
        </Button>
      </FormFooter>
      {canAct && <Problems items={problems} />}
    </form>
  );
}
