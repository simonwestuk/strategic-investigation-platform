"use client";

import { CLASSIFICATION_META, CLASSIFICATION_ORDER } from "@/lib/labels";
import { type CommonReviewState, MAX_ADDITIONAL_ITERATIONS } from "@/lib/reviews";
import type { Claim, Classification } from "@/lib/types";
import { inputClass, labelClass } from "../../ui/Button";

const truncate = (s: string, n = 110) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/**
 * Inputs every review kind accepts: a note, a human challenge, a research request, a classification
 * override and extra research iterations. Free text passes through the privacy gateway server-side.
 */
export function CommonReviewFields({
  value,
  onChange,
  claims,
  idPrefix,
}: {
  value: CommonReviewState;
  onChange: (next: CommonReviewState) => void;
  claims: readonly Claim[];
  idPrefix: string;
}) {
  const set = <K extends keyof CommonReviewState>(k: K, v: CommonReviewState[K]) => onChange({ ...value, [k]: v });
  const id = (s: string) => `${idPrefix}-${s}`;
  const activeClaims = claims.filter((c) => c.active);

  return (
    <div className="space-y-3">
      <div>
        <label htmlFor={id("note")} className={labelClass}>
          Note to the record (optional)
        </label>
        <textarea id={id("note")} rows={2} className={inputClass} value={value.note} onChange={(e) => set("note", e.target.value)} />
      </div>
      <details className="rounded border border-line bg-surface-muted/50 px-3 py-2">
        <summary className="flex items-center gap-1 text-[13px] font-medium text-ink">
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Challenge, request research, override a classification or extend iterations (optional)
        </summary>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <fieldset className="space-y-2">
            <legend className="text-xs font-semibold text-ink">Challenge a claim or assumption</legend>
            <div>
              <label htmlFor={id("ch-target")} className={labelClass}>
                Target
              </label>
              <select id={id("ch-target")} className={inputClass} value={value.challengeTargetId} onChange={(e) => set("challengeTargetId", e.target.value)}>
                <option value="">Select…</option>
                <option value="investigation">The investigation as a whole (framing / assumptions)</option>
                {activeClaims.map((c) => (
                  <option key={c.id} value={c.id}>
                    [{CLASSIFICATION_META[c.classification].label}] {truncate(c.statement)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor={id("ch-arg")} className={labelClass}>
                Argument
              </label>
              <textarea id={id("ch-arg")} rows={2} className={inputClass} value={value.challengeArgument} onChange={(e) => set("challengeArgument", e.target.value)} />
            </div>
          </fieldset>
          <fieldset className="space-y-2">
            <legend className="text-xs font-semibold text-ink">Override a classification</legend>
            <div>
              <label htmlFor={id("ov-claim")} className={labelClass}>
                Claim
              </label>
              <select id={id("ov-claim")} className={inputClass} value={value.overrideClaimId} onChange={(e) => set("overrideClaimId", e.target.value)}>
                <option value="">Select…</option>
                {activeClaims.map((c) => (
                  <option key={c.id} value={c.id}>
                    [{CLASSIFICATION_META[c.classification].label}] {truncate(c.statement)}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-[10rem_1fr] gap-2">
              <div>
                <label htmlFor={id("ov-class")} className={labelClass}>
                  New classification
                </label>
                <select
                  id={id("ov-class")}
                  className={inputClass}
                  value={value.overrideClassification}
                  onChange={(e) => set("overrideClassification", e.target.value as Classification | "")}
                >
                  <option value="">Select…</option>
                  {CLASSIFICATION_ORDER.map((c) => (
                    <option key={c} value={c}>
                      {CLASSIFICATION_META[c].label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor={id("ov-reason")} className={labelClass}>
                  Reason (recorded)
                </label>
                <input id={id("ov-reason")} className={inputClass} value={value.overrideReason} onChange={(e) => set("overrideReason", e.target.value)} />
              </div>
            </div>
          </fieldset>
          <div>
            <label htmlFor={id("rr")} className={labelClass}>
              Research request
            </label>
            <textarea
              id={id("rr")}
              rows={2}
              className={inputClass}
              placeholder="e.g. Obtain employer destination data for lost DTS accounts"
              value={value.researchRequest}
              onChange={(e) => set("researchRequest", e.target.value)}
            />
          </div>
          <div>
            <label htmlFor={id("iters")} className={labelClass}>
              Additional research iterations (0–{MAX_ADDITIONAL_ITERATIONS})
            </label>
            <input
              id={id("iters")}
              type="number"
              min={0}
              max={MAX_ADDITIONAL_ITERATIONS}
              className={`${inputClass} w-24`}
              value={value.additionalIterations}
              onChange={(e) =>
                set("additionalIterations", Math.max(0, Math.min(MAX_ADDITIONAL_ITERATIONS, Math.trunc(Number(e.target.value) || 0))))
              }
            />
          </div>
        </div>
      </details>
    </div>
  );
}
