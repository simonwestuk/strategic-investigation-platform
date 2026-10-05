"use client";

import { useState } from "react";
import { parseClarificationContext } from "@/lib/review-context";
import { type CommonReviewState, EMPTY_COMMON, buildResponse, commonProblems } from "@/lib/reviews";
import { Button } from "../../ui/Button";
import { BulletList } from "../../ui/Panel";
import { CommonReviewFields } from "./CommonReviewFields";
import { FormFooter, Problems } from "./FormFooter";
import type { ReviewFormProps } from "./types";
import { useSubmit } from "./useSubmit";

/** The framer found the question ambiguous. The note carries the clarification back into framing. */
export function ClarificationForm({ review, claims, canAct, onSubmit }: ReviewFormProps) {
  const ctx = parseClarificationContext(review.context);
  const [common, setCommon] = useState<CommonReviewState>(EMPTY_COMMON);
  const { busy, error, run } = useSubmit(onSubmit);
  const problems = [...(common.note.trim() ? [] : ["Answer the clarification questions in the note."]), ...commonProblems(common)];

  return (
    <form aria-label="Clarification" className="space-y-4" onSubmit={(e) => e.preventDefault()}>
      {ctx.subject && <p className="text-[13px] text-ink-muted">Subject: {ctx.subject}</p>}
      <BulletList items={ctx.questions} />
      <fieldset disabled={!canAct || busy}>
        <CommonReviewFields value={common} onChange={setCommon} claims={claims} idPrefix={`clr-${review.id}`} />
      </fieldset>
      <FormFooter error={error}>
        <Button
          variant="primary"
          disabled={!canAct || busy || problems.length > 0}
          onClick={() => void run(buildResponse("approve", common))}
        >
          Submit clarification
        </Button>
        {review.allowed_actions.includes("reject") && (
          <Button variant="danger" disabled={!canAct || busy} onClick={() => void run(buildResponse("reject", common))}>
            Close investigation
          </Button>
        )}
      </FormFooter>
      {canAct && <Problems items={problems} />}
    </form>
  );
}
