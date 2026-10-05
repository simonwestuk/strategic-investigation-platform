import clsx from "clsx";
import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-surface border-accent hover:opacity-90",
  secondary: "bg-surface text-ink border-line-strong hover:bg-surface-muted",
  ghost: "bg-transparent text-accent border-transparent hover:bg-accent-soft",
  danger: "bg-surface text-danger-fg border-danger-fg/50 hover:bg-danger-bg",
};

export function Button({
  variant = "secondary",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type={type}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded border px-3 py-1.5 text-[13px] font-medium",
        "disabled:cursor-not-allowed disabled:opacity-50",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}

/** Inline text-styled button for navigating to a claim/source/etc. */
export function LinkButton({ className, type = "button", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type={type}
      className={clsx("text-left text-accent underline decoration-accent/30 underline-offset-2 hover:decoration-accent", className)}
      {...props}
    />
  );
}

export const inputClass =
  "w-full rounded border border-line-strong bg-surface px-2.5 py-1.5 text-[13px] text-ink placeholder:text-ink-subtle disabled:opacity-60";

export const labelClass = "mb-1 block text-xs font-medium text-ink-muted";
