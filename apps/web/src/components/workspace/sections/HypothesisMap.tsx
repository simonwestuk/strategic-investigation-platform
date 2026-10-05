"use client";

import { claimsForHypothesis, evidenceStanceCounts } from "@/lib/decision-room";
import { humanise } from "@/lib/format";
import { HYPOTHESIS_STATUS_LABELS } from "@/lib/labels";
import type { Hypothesis, HypothesisStatus } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { LinkButton } from "../../ui/Button";
import { ClassificationBadge } from "../../ui/ClassificationBadge";
import { BulletList, EmptyState, SectionHeading } from "../../ui/Panel";
import { HypothesisStatusBadge, OriginBadge } from "../../ui/StatusBadges";
import { useWorkspace } from "../WorkspaceContext";

function Node({ h, kids }: { h: Hypothesis; kids: Hypothesis[] }) {
  const { detail, openClaim } = useWorkspace();
  const claims = claimsForHypothesis(detail.claims, h.id);
  const stance = evidenceStanceCounts(detail.evidence, h.id);
  return (
    <li className="relative">
      <div
        className={`rounded-md border bg-surface px-3 py-2.5 ${h.status === "unresolved" ? "border-dashed border-unknown-line" : "border-line"}`}
      >
        <div className="flex flex-wrap items-center gap-1.5">
          <HypothesisStatusBadge status={h.status} />
          <OriginBadge origin={h.origin} />
          <Badge tone="muted">{humanise(h.category)}</Badge>
          {h.segment && <Badge tone="accent">Segment: {detail.segment_names?.[h.segment] ?? h.segment}</Badge>}
          <Badge tone="muted">Priority {h.priority}</Badge>
          <span className="ml-auto text-[11px] text-ink-subtle">
            evidence: <span className="text-ok-fg">{stance.supports} for</span> ·{" "}
            <span className="text-danger-fg">{stance.contradicts} against</span>
          </span>
        </div>
        <p className="mt-1.5 text-[13px] font-medium leading-snug">{h.statement}</p>
        <p className="mt-0.5 text-xs text-ink-muted">
          <span className="font-medium">Status reason:</span> {h.status_reason || "—"}
        </p>
        <details className="mt-1 text-xs">
          <summary className="inline-flex items-center gap-1 text-accent">
            <span className="chevron" aria-hidden="true">
              ›
            </span>
            Rationale and tests
          </summary>
          <div className="mt-1.5 grid gap-3 md:grid-cols-3">
            <p className="text-ink-muted">{h.rationale}</p>
            <div>
              <p className="font-medium">Would support</p>
              <BulletList items={h.would_support} empty="—" />
            </div>
            <div>
              <p className="font-medium">Would contradict</p>
              <BulletList items={h.would_contradict} empty="—" />
            </div>
          </div>
        </details>
        {claims.length > 0 && (
          <div className="mt-2 border-t border-line pt-2">
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-subtle">Linked claims ({claims.length})</p>
            <ul className="space-y-1">
              {claims.map((c) => (
                <li key={c.id} className="flex items-start gap-2 text-[13px]">
                  <ClassificationBadge classification={c.classification} />
                  <LinkButton onClick={() => openClaim(c.id)} className="leading-snug">
                    {c.statement}
                  </LinkButton>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {kids.length > 0 && (
        <ul className="ml-4 mt-2 space-y-2 border-l-2 border-line pl-4" aria-label={`Segment refinements of ${h.category}`}>
          {kids.map((c) => (
            <Node key={c.id} h={c} kids={[]} />
          ))}
        </ul>
      )}
    </li>
  );
}

const ORDER: HypothesisStatus[] = ["split", "supported", "weakened", "contradicted", "investigating", "unresolved", "proposed"];

export function HypothesisMap() {
  const { detail } = useWorkspace();
  const hs = detail.hypotheses;
  const ids = new Set(hs.map((h) => h.id));
  const roots = hs.filter((h) => !h.parent_id || !ids.has(h.parent_id));
  const children = (id: string) => hs.filter((h) => h.parent_id === id);
  const counts = ORDER.map((s) => [s, hs.filter((h) => h.status === s).length] as const).filter(([, n]) => n > 0);

  return (
    <div>
      <SectionHeading
        title="Hypothesis map"
        description="Competing explanations generated at framing (initial), from evidence (emergent), by the sceptic (challenger) or by reviewers (human). Drivers whose evidence diverged by segment are split into segment children."
      />
      <div className="mb-4 flex flex-wrap gap-2 text-xs">
        {counts.map(([s, n]) => (
          <span key={s} className="flex items-center gap-1">
            <HypothesisStatusBadge status={s} />
            <span className="text-ink-muted" aria-label={`${n} ${HYPOTHESIS_STATUS_LABELS[s]}`}>
              {n}
            </span>
          </span>
        ))}
      </div>
      {roots.length === 0 ? (
        <EmptyState>No hypotheses yet.</EmptyState>
      ) : (
        <ul className="space-y-3">
          {roots.map((r) => (
            <Node key={r.id} h={r} kids={children(r.id)} />
          ))}
        </ul>
      )}
    </div>
  );
}
