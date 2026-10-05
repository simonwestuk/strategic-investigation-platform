"use client";

import clsx from "clsx";
import { bucketKnowledge } from "@/lib/decision-room";
import { type SectionId, SECTIONS } from "./sections";
import { useWorkspace } from "./WorkspaceContext";

export function SectionNav({ current }: { current: SectionId }) {
  const { detail } = useWorkspace();
  const b = bucketKnowledge(detail);
  const pending = detail.reviews.some((r) => r.status === "pending");
  const counts: Partial<Record<SectionId, number | string>> = {
    hypotheses: detail.hypotheses.length,
    research: detail.tasks.length,
    evidence: detail.evidence.length,
    claims: detail.claims.filter((c) => c.active).length,
    challenges: b.contradictions.length + b.openChallenges.length,
    governance: pending ? "1 pending" : detail.reviews.length,
    privacy: detail.intake.length,
    audit: detail.audit_count,
  };
  return (
    <nav aria-label="Workspace sections" className="lg:sticky lg:top-4 lg:self-start">
      <ul className="flex gap-1 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible lg:pb-0">
        {SECTIONS.map((s) => {
          const active = s.id === current;
          const count = counts[s.id];
          return (
            <li key={s.id} className="shrink-0">
              <a
                href={`#${s.id}`}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-center justify-between gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-[13px]",
                  active ? "bg-accent-soft font-semibold text-accent" : "text-ink hover:bg-surface-muted",
                )}
              >
                <span>{s.label}</span>
                {count !== undefined && (
                  <span
                    className={clsx(
                      "text-[11px]",
                      s.id === "governance" && pending ? "rounded bg-warn-bg px-1 font-semibold text-warn-fg" : "text-ink-subtle",
                    )}
                  >
                    {count}
                  </span>
                )}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
