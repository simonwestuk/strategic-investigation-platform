"use client";

import clsx from "clsx";
import { type ReactNode, useState } from "react";
import type { KnowledgeBuckets } from "@/lib/decision-room";
import { humanise } from "@/lib/format";
import type { Claim, Classification } from "@/lib/types";
import { CLASSIFICATION_RULE } from "../../ui/ClassificationBadge";
import { Badge } from "../../ui/Badge";
import { LinkButton } from "../../ui/Button";
import { HypothesisStatusBadge, SeverityBadge } from "../../ui/StatusBadges";
import { ClaimRef } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

const PREVIEW = 5;

function Column({
  heading,
  hint,
  rule,
  count,
  children,
}: {
  heading: string;
  hint: string;
  rule: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section className="flex min-w-0 flex-col rounded-md border border-line bg-surface">
      <header className={clsx("rounded-t-md px-3 pb-2 pt-2.5", rule)}>
        <h3 className="flex items-baseline justify-between gap-2 text-xs font-bold tracking-wider text-ink">
          {heading}
          <span className="font-normal text-ink-subtle">{count}</span>
        </h3>
        <p className="mt-0.5 text-[11.5px] leading-snug text-ink-muted">{hint}</p>
      </header>
      <div className="flex-1 space-y-3 border-t border-line px-3 py-3">{children}</div>
    </section>
  );
}

function ClaimList({ claims, onOpen }: { claims: Claim[]; onOpen: (id: string) => void }) {
  const [all, setAll] = useState(false);
  const shown = all ? claims : claims.slice(0, PREVIEW);
  if (claims.length === 0) return <p className="text-[13px] text-ink-subtle">None.</p>;
  return (
    <>
      <ul className="space-y-3">
        {shown.map((c) => (
          <li key={c.id}>
            <ClaimRef claim={c} onOpen={onOpen} />
          </li>
        ))}
      </ul>
      {claims.length > PREVIEW && (
        <button type="button" className="text-xs text-accent hover:underline" onClick={() => setAll((v) => !v)}>
          {all ? "Show fewer" : `Show all ${claims.length}`}
        </button>
      )}
    </>
  );
}

const rule = (c: Classification) => CLASSIFICATION_RULE[c];

export function KnowledgeColumns({ buckets }: { buckets: KnowledgeBuckets }) {
  const { openClaim, lookups, goTo } = useWorkspace();
  const contradicting = buckets.contradictions.length + buckets.openChallenges.length;

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Column heading="WHAT WE KNOW" hint="Established by authoritative, current evidence." rule={rule("known")} count={buckets.known.length}>
        <ClaimList claims={buckets.known} onOpen={openClaim} />
      </Column>
      <Column heading="WHAT WE INFER" hint="Follows from evidence via a stated inferential step." rule={rule("inferred")} count={buckets.inferred.length}>
        <ClaimList claims={buckets.inferred} onOpen={openClaim} />
      </Column>
      <Column
        heading="WHAT REMAINS UNKNOWN"
        hint="Unknowns, unestablished hypotheses and unresolved drivers."
        rule={rule("unknown")}
        count={buckets.unknown.length + buckets.unresolvedHypotheses.length}
      >
        <ClaimList claims={buckets.unknown} onOpen={openClaim} />
        {buckets.unresolvedHypotheses.length > 0 && (
          <div className="border-t border-dashed border-line pt-2">
            <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-subtle">Unresolved hypotheses</p>
            <ul className="space-y-2">
              {buckets.unresolvedHypotheses.map((h) => (
                <li key={h.id} className="text-[13px]">
                  <HypothesisStatusBadge status={h.status} />
                  <p className="mt-0.5 leading-snug">{h.statement}</p>
                  <p className="text-xs text-ink-muted">{h.status_reason}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Column>
      <Column
        heading="WHAT CONTRADICTS THE CURRENT EXPLANATION"
        hint="Unresolved evidence conflicts and open sceptic challenges."
        rule="border-t-[3px] border-solid border-danger-fg"
        count={contradicting}
      >
        {contradicting === 0 && <p className="text-[13px] text-ink-subtle">None open.</p>}
        <ul className="space-y-3">
          {buckets.contradictions.map((c) => (
            <li key={c.id} className="text-[13px]">
              <Badge tone="warn">Contradiction · {c.supporting_evidence_ids.length} for / {c.contradicting_evidence_ids.length} against</Badge>
              <p className="mt-0.5 leading-snug">{c.description}</p>
            </li>
          ))}
          {buckets.openChallenges.map((c) => {
            const target = lookups.claims.get(c.target_id);
            return (
              <li key={c.id} className="text-[13px]">
                <span className="flex flex-wrap gap-1">
                  <Badge tone="muted">Challenge · {humanise(c.kind)}</Badge>
                  <SeverityBadge severity={c.severity} />
                </span>
                <p className="mt-0.5 leading-snug">{c.argument}</p>
                {target && (
                  <LinkButton className="text-xs" onClick={() => openClaim(target.id)}>
                    On: {target.statement}
                  </LinkButton>
                )}
              </li>
            );
          })}
        </ul>
        {contradicting > 0 && (
          <button type="button" className="text-xs text-accent hover:underline" onClick={() => goTo("challenges")}>
            All contradictions &amp; challenges →
          </button>
        )}
      </Column>
    </div>
  );
}
