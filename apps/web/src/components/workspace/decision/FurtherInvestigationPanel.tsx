"use client";

import type { FurtherInvestigationItem } from "@/lib/decision-room";
import { Badge } from "../../ui/Badge";
import { LinkButton } from "../../ui/Button";
import { BulletList, EmptyState, Panel } from "../../ui/Panel";
import { useWorkspace } from "../WorkspaceContext";

export function FurtherInvestigationPanel({ items }: { items: FurtherInvestigationItem[] }) {
  const { openClaim } = useWorkspace();
  return (
    <Panel
      title="Further investigation"
      subtitle="What could not be resolved with the available evidence, and what would resolve it."
    >
      {items.length === 0 ? (
        <EmptyState>No outstanding evidence gaps.</EmptyState>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {items.map((it) => (
            <li key={it.id} className="rounded border border-dashed border-unknown-line px-3 py-2">
              <Badge tone={it.kind === "blocked_task" ? "warn" : "muted"} className="border-dashed">
                {it.kind === "blocked_task" ? "Research blocked — data unavailable" : "? UNKNOWN claim"}
              </Badge>
              {it.claimId ? (
                <LinkButton className="mt-1 block text-[13px]" onClick={() => openClaim(it.claimId as string)}>
                  {it.title}
                </LinkButton>
              ) : (
                <p className="mt-1 text-[13px]">{it.title}</p>
              )}
              <div className="mt-1.5 text-ink-muted">
                <p className="mb-0.5 text-xs font-medium">What is needed</p>
                <BulletList items={it.needs} />
              </div>
              {it.nextQuestion && (
                <p className="mt-1.5 text-xs">
                  <span className="font-medium">Next question: </span>
                  {it.nextQuestion}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
