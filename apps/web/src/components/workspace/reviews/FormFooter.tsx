import type { ReactNode } from "react";
import { ErrorNotice } from "../../ErrorNotice";

export function Problems({ items }: { items: readonly string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="list-disc space-y-0.5 pl-5 text-xs text-ink-muted" aria-live="polite">
      {items.map((p) => (
        <li key={p}>{p}</li>
      ))}
    </ul>
  );
}

export function FormFooter({ error, children }: { error: Error | null; children: ReactNode }) {
  return (
    <div className="space-y-2 border-t border-line pt-3">
      {error && <ErrorNotice error={error} context="The response was not recorded" />}
      <div className="flex flex-wrap items-center gap-2">{children}</div>
    </div>
  );
}
