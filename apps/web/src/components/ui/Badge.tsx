import clsx from "clsx";
import type { ReactNode } from "react";

export type Tone = "neutral" | "ok" | "warn" | "danger" | "info" | "ai" | "accent" | "muted";

const TONES: Record<Tone, string> = {
  neutral: "bg-surface-muted text-ink border-line",
  muted: "bg-transparent text-ink-muted border-line",
  ok: "bg-ok-bg text-ok-fg border-transparent",
  warn: "bg-warn-bg text-warn-fg border-transparent",
  danger: "bg-danger-bg text-danger-fg border-transparent",
  info: "bg-info-bg text-info-fg border-transparent",
  ai: "bg-ai-bg text-ai-fg border-ai-line",
  accent: "bg-accent-soft text-accent border-transparent",
};

export function Badge({
  tone = "neutral",
  children,
  title,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  title?: string;
  className?: string;
}) {
  return (
    <span
      title={title}
      className={clsx(
        "inline-flex items-center gap-1 whitespace-nowrap rounded border px-1.5 py-px text-[11px] font-medium leading-4",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
