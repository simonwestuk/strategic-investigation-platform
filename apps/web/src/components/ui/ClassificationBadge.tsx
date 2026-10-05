import clsx from "clsx";
import { CLASSIFICATION_META } from "@/lib/labels";
import type { Classification } from "@/lib/types";

export const CLASSIFICATION_STYLES: Record<Classification, string> = {
  known: "bg-known-bg text-known-fg border-known-line border-solid",
  inferred: "bg-inferred-bg text-inferred-fg border-inferred-line border-solid",
  hypothesis: "bg-hypothesis-bg text-hypothesis-fg border-hypothesis-line border-dotted",
  unknown: "bg-unknown-bg text-unknown-fg border-unknown-line border-dashed",
};

/** Thick top rule for an element that has no other border (style differs per class, not just colour). */
export const CLASSIFICATION_RULE: Record<Classification, string> = {
  known: "border-t-[3px] border-solid border-known-line",
  inferred: "border-t-[3px] border-solid border-inferred-line",
  hypothesis: "border-t-[3px] border-dotted border-hypothesis-line",
  unknown: "border-t-[3px] border-dashed border-unknown-line",
};

/**
 * Epistemic classification. Always shows a text label and a glyph; UNKNOWN uses a dashed outline
 * and HYPOTHESIS a dotted one, so the distinction never depends on colour alone.
 */
export function ClassificationBadge({
  classification,
  proposed,
  size = "sm",
}: {
  classification: Classification;
  /** Classification the analyst proposed before the confidence rubric applied its ceiling. */
  proposed?: Classification;
  size?: "sm" | "md";
}) {
  const meta = CLASSIFICATION_META[classification];
  const downgraded = proposed !== undefined && proposed !== classification;
  return (
    <span className="inline-flex items-center gap-1">
      <span
        role="img"
        aria-label={`Classification: ${meta.label}`}
        title={meta.description}
        data-classification={classification}
        className={clsx(
          "inline-flex items-center gap-1 rounded border font-semibold tracking-wide",
          size === "sm" ? "px-1.5 py-px text-[10.5px] leading-4" : "px-2 py-0.5 text-xs",
          CLASSIFICATION_STYLES[classification],
        )}
      >
        <span aria-hidden="true">{meta.glyph}</span>
        <span aria-hidden="true">{meta.label}</span>
      </span>
      {downgraded && (
        <span
          className="text-[11px] text-ink-muted"
          title="The deterministic confidence rubric capped this claim below the analyst's proposal."
        >
          rubric capped from {CLASSIFICATION_META[proposed].label}
        </span>
      )}
    </span>
  );
}
