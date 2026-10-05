"use client";

import { useState } from "react";
import { DECISION_TYPE_LABELS } from "@/lib/labels";
import { parseDecisionContext } from "@/lib/review-context";
import {
  type CommonReviewState,
  type DecisionFormState,
  EMPTY_COMMON,
  EMPTY_DECISION,
  buildResponse,
  commonProblems,
  decisionPayload,
  decisionProblems,
  toggle,
} from "@/lib/reviews";
import type { DecisionType, StrategicOption } from "@/lib/types";
import { Button, inputClass, labelClass } from "../../ui/Button";
import { ConfidenceMeter } from "../../ui/ConfidenceMeter";
import { OptionReviewBadge } from "../../ui/StatusBadges";
import { CommonReviewFields } from "./CommonReviewFields";
import { FormFooter, Problems } from "./FormFooter";
import type { ReviewFormProps } from "./types";
import { useSubmit } from "./useSubmit";

/**
 * The only place a Decision is recorded. The decision-maker must explicitly acknowledge every
 * unresolved UNKNOWN the platform surfaced, plus the stated uncertainties, before submitting.
 */
export function DecisionForm({
  review,
  claims,
  canAct,
  onSubmit,
  options,
}: ReviewFormProps & { options: readonly StrategicOption[] }) {
  const ctx = parseDecisionContext(review.context);
  const unknownIds = ctx.unknowns.map((u) => u.id);
  const [form, setForm] = useState<DecisionFormState>(EMPTY_DECISION);
  const [common, setCommon] = useState<CommonReviewState>(EMPTY_COMMON);
  const { busy, error, run } = useSubmit(onSubmit);
  const set = <K extends keyof DecisionFormState>(k: K, v: DecisionFormState[K]) => setForm((f) => ({ ...f, [k]: v }));

  const problems = [...decisionProblems(form, unknownIds), ...commonProblems(common)];
  const canDecide = canAct && !busy && problems.length === 0;
  const canRequest =
    canAct && !busy && review.allowed_actions.includes("request_further_investigation") && commonProblems(common).length === 0;
  const optionById = new Map(options.map((o) => [o.id, o]));
  const decisionTypes = (ctx.decisionTypes.length ? ctx.decisionTypes : Object.keys(DECISION_TYPE_LABELS)) as DecisionType[];

  return (
    <form
      aria-label="Record a decision"
      onSubmit={(e) => {
        e.preventDefault();
        if (canDecide) void run(buildResponse("decide", common, { decision: decisionPayload(form, unknownIds) }));
      }}
      className="space-y-4"
    >
      <fieldset disabled={!canAct || busy} className="space-y-4">
        <div className="grid gap-3 md:grid-cols-[16rem_1fr]">
          <div>
            <label htmlFor="decision-type" className={labelClass}>
              Decision type
            </label>
            <select
              id="decision-type"
              className={inputClass}
              value={form.decisionType}
              onChange={(e) => set("decisionType", e.target.value as DecisionType | "")}
            >
              <option value="">Select…</option>
              {decisionTypes.map((t) => (
                <option key={t} value={t}>
                  {DECISION_TYPE_LABELS[t] ?? t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="decision-statement" className={labelClass}>
              Decision statement
            </label>
            <input
              id="decision-statement"
              className={inputClass}
              value={form.statement}
              onChange={(e) => set("statement", e.target.value)}
              placeholder="What has been decided, in one sentence"
            />
          </div>
        </div>
        <div>
          <label htmlFor="decision-rationale" className={labelClass}>
            Rationale
          </label>
          <textarea id="decision-rationale" rows={3} className={inputClass} value={form.rationale} onChange={(e) => set("rationale", e.target.value)} />
        </div>

        <fieldset>
          <legend className={labelClass}>Options this decision relates to (AI recommendations approved for decision)</legend>
          <ul className="grid gap-1.5 md:grid-cols-2">
            {ctx.options.map((o) => {
              const full = optionById.get(o.id);
              return (
                <li key={o.id}>
                  <label className="flex items-start gap-2 rounded border border-line px-2.5 py-1.5 text-[13px] hover:bg-surface-muted">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={form.optionIds.includes(o.id)}
                      onChange={() => set("optionIds", toggle(form.optionIds, o.id))}
                    />
                    <span className="min-w-0">
                      <span className="block">{o.title}</span>
                      {full && (
                        <span className="mt-0.5 flex flex-wrap items-center gap-2">
                          <ConfidenceMeter band={full.confidence_band} />
                          <OptionReviewBadge status={full.review_status} />
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </fieldset>

        <div>
          <label htmlFor="decision-conditions" className={labelClass}>
            Conditions (one per line, optional)
          </label>
          <textarea
            id="decision-conditions"
            rows={2}
            className={inputClass}
            value={form.conditions}
            onChange={(e) => set("conditions", e.target.value)}
            placeholder="e.g. Revisit if the destination survey shows category exit"
          />
        </div>

        <fieldset className="rounded border border-dashed border-unknown-line bg-unknown-bg p-3">
          <legend className="px-1 text-xs font-semibold text-ink">Required acknowledgements</legend>
          {ctx.unknowns.length > 0 && (
            <>
              <p className="mb-2 text-xs text-ink-muted">
                The evidence could not resolve the following. Acknowledge each one to confirm the decision is taken knowing it
                remains UNKNOWN.
              </p>
              <ul className="mb-3 space-y-1.5">
                {ctx.unknowns.map((u) => (
                  <li key={u.id}>
                    <label className="flex items-start gap-2 text-[13px]">
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={form.acknowledgedUnknownIds.includes(u.id)}
                        onChange={() => set("acknowledgedUnknownIds", toggle(form.acknowledgedUnknownIds, u.id))}
                      />
                      <span>
                        <span className="mr-1 font-semibold text-unknown-fg">? UNKNOWN</span>
                        {u.statement}
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </>
          )}
          <label className="flex items-start gap-2 text-[13px] font-medium">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={form.uncertaintiesAcknowledged}
              onChange={(e) => set("uncertaintiesAcknowledged", e.target.checked)}
            />
            I acknowledge the stated uncertainties, and that the options above are AI recommendations, not decisions.
          </label>
        </fieldset>

        <CommonReviewFields value={common} onChange={setCommon} claims={claims} idPrefix={`dec-${review.id}`} />
      </fieldset>

      <FormFooter error={error}>
        <Button type="submit" variant="primary" disabled={!canDecide}>
          {busy ? "Recording…" : "Record decision"}
        </Button>
        {review.allowed_actions.includes("request_further_investigation") && (
          <Button
            variant="secondary"
            disabled={!canRequest}
            onClick={() => void run(buildResponse("request_further_investigation", common))}
          >
            Request further investigation instead
          </Button>
        )}
        <span className="text-xs text-ink-muted">Recorded under your identity with a timestamp in the audit trail.</span>
      </FormFooter>
      {canAct && <Problems items={problems} />}
    </form>
  );
}
