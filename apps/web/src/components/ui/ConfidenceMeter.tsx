import clsx from "clsx";
import { CONFIDENCE_LABELS, CONFIDENCE_PIPS } from "@/lib/labels";
import type { ConfidenceBand } from "@/lib/types";

export function ConfidenceMeter({ band, score }: { band: ConfidenceBand; score?: number }) {
  const filled = CONFIDENCE_PIPS[band];
  const label = `${CONFIDENCE_LABELS[band]} confidence${score !== undefined ? ` (rubric score ${score})` : ""}`;
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-ink-muted" title={label}>
      <span className="inline-flex gap-0.5" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={clsx("h-2.5 w-1.5 rounded-[1px]", i < filled ? "bg-ink-muted" : "border border-line-strong")}
          />
        ))}
      </span>
      <span>
        <span className="sr-only">{label}</span>
        <span aria-hidden="true">{CONFIDENCE_LABELS[band]}</span>
      </span>
    </span>
  );
}
