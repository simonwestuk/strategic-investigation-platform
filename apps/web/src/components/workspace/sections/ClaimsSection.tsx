"use client";

import { useState } from "react";
import { CLASSIFICATION_META, CLASSIFICATION_ORDER } from "@/lib/labels";
import { pluralise } from "@/lib/format";
import { Badge } from "../../ui/Badge";
import { CLASSIFICATION_RULE } from "../../ui/ClassificationBadge";
import { EmptyState, SectionHeading } from "../../ui/Panel";
import { ClaimRef } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

export function ClaimsSection() {
  const { detail, openClaim } = useWorkspace();
  const [showInactive, setShowInactive] = useState(false);
  const claims = detail.claims.filter((c) => showInactive || c.active);
  const capped = claims.filter((c) => c.classification !== c.proposed_classification).length;

  return (
    <div>
      <SectionHeading
        title="Claims"
        description="Every claim is classified by a deterministic confidence rubric. The rubric can cap an analyst's proposal (e.g. stale or secondary-tier evidence cannot support KNOWN). Open a claim for its full chain."
        actions={
          <label className="flex items-center gap-1.5 text-xs text-ink-muted">
            <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
            Include superseded claims
          </label>
        }
      />
      <p className="mb-4 text-xs text-ink-muted">
        {pluralise(claims.length, "claim")} · {capped} capped by the rubric ·{" "}
        {claims.filter((c) => c.human_override).length} overridden by a human
      </p>
      {claims.length === 0 && <EmptyState>No claims yet.</EmptyState>}
      <div className="space-y-5">
        {CLASSIFICATION_ORDER.map((cls) => {
          const group = claims
            .filter((c) => c.classification === cls)
            .sort((a, b) => (b.confidence?.score ?? 0) - (a.confidence?.score ?? 0));
          if (group.length === 0) return null;
          const meta = CLASSIFICATION_META[cls];
          return (
            <section key={cls} className="rounded-md border border-line bg-surface">
              <header className={`rounded-t-md px-4 py-2 ${CLASSIFICATION_RULE[cls]}`}>
                <h3 className="text-[13px] font-bold tracking-wider">
                  {meta.label} <span className="font-normal text-ink-subtle">({group.length})</span>
                </h3>
                <p className="text-xs text-ink-muted">{meta.description}</p>
              </header>
              <ul className="divide-y divide-line border-t border-line">
                {group.map((c) => (
                  <li key={c.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-2.5">
                    <ClaimRef claim={c} onOpen={openClaim} className="min-w-0 flex-1" />
                    <div className="flex shrink-0 flex-col items-end gap-1 text-[11px] text-ink-muted">
                      <span className="tabular-nums">
                        <span className="text-ok-fg">{c.supporting_evidence_ids.length} for</span> ·{" "}
                        <span className="text-danger-fg">{c.contradicting_evidence_ids.length} against</span>
                      </span>
                      <span className="flex gap-1">
                        {c.causal && <Badge tone="muted">Causal</Badge>}
                        {!c.active && <Badge tone="warn">Superseded</Badge>}
                        {c.review_state !== "unreviewed" && <Badge tone="accent">{c.review_state}</Badge>}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          );
        })}
      </div>
    </div>
  );
}
