"use client";

import { formatDateTime, humanise } from "@/lib/format";
import type { Contradiction, Evidence } from "@/lib/types";
import { Badge } from "../../ui/Badge";
import { LinkButton } from "../../ui/Button";
import { EmptyState, SectionHeading } from "../../ui/Panel";
import { ChallengeStatusBadge, ContradictionStatusBadge, SeverityBadge } from "../../ui/StatusBadges";
import { EvidenceCard } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

function ContradictionCard({ c }: { c: Contradiction }) {
  const { lookups, openClaim, openSource } = useWorkspace();
  const ev = (ids: string[]) => ids.map((id) => lookups.evidence.get(id)).filter((e): e is Evidence => Boolean(e));
  const hyp = c.hypothesis_id ? lookups.hypotheses.get(c.hypothesis_id) : undefined;
  return (
    <li className="rounded-md border border-line bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <ContradictionStatusBadge status={c.status} />
        <span className="text-xs text-ink-muted">
          {c.supporting_evidence_ids.length} supporting vs {c.contradicting_evidence_ids.length} contradicting
        </span>
      </div>
      <p className="mt-1 text-[13px]">{c.description}</p>
      {hyp && <p className="mt-0.5 text-xs text-ink-muted">Hypothesis: {hyp.statement}</p>}
      {c.claim_id && (
        <LinkButton className="mt-0.5 text-xs" onClick={() => openClaim(c.claim_id as string)}>
          Open the claim
        </LinkButton>
      )}
      {c.resolution_note && <p className="mt-1 rounded bg-surface-muted px-2 py-1 text-xs">Resolution: {c.resolution_note}</p>}
      <details className="mt-2 text-xs">
        <summary className="inline-flex items-center gap-1 text-accent">
          <span className="chevron" aria-hidden="true">
            ›
          </span>
          Compare the evidence
        </summary>
        <div className="mt-2 grid gap-2 lg:grid-cols-2">
          <div className="space-y-2">
            {ev(c.supporting_evidence_ids).map((e) => (
              <EvidenceCard key={e.id} evidence={e} source={lookups.sources.get(e.source_id)} stance="supports" onOpenSource={openSource} />
            ))}
          </div>
          <div className="space-y-2">
            {ev(c.contradicting_evidence_ids).map((e) => (
              <EvidenceCard key={e.id} evidence={e} source={lookups.sources.get(e.source_id)} stance="contradicts" onOpenSource={openSource} />
            ))}
          </div>
        </div>
      </details>
    </li>
  );
}

export function ChallengesSection() {
  const { detail, lookups, openClaim } = useWorkspace();
  const contradictions = [...detail.contradictions].sort((a, b) => Number(b.status === "unresolved") - Number(a.status === "unresolved"));
  const challenges = [...detail.challenges].sort((a, b) => Number(b.status === "open") - Number(a.status === "open"));
  return (
    <div className="space-y-8">
      <div>
        <SectionHeading
          title="Contradictions"
          description="Where evidence of comparable standing points in opposite directions. Resolved either by source quality, by explanation or by a human."
        />
        {contradictions.length === 0 ? (
          <EmptyState>No contradictions recorded.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {contradictions.map((c) => (
              <ContradictionCard key={c.id} c={c} />
            ))}
          </ul>
        )}
      </div>
      <div>
        <SectionHeading
          title="Challenges"
          description="Raised by the sceptic agent (or by human reviewers) against claims and hypotheses. Open blocking challenges stop findings from being accepted without human review."
        />
        {challenges.length === 0 ? (
          <EmptyState>No challenges raised.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {challenges.map((c) => {
              const claim = lookups.claims.get(c.target_id);
              const hyp = lookups.hypotheses.get(c.target_id);
              return (
                <li key={c.id} className="rounded-md border border-line bg-surface px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <ChallengeStatusBadge status={c.status} />
                    <SeverityBadge severity={c.severity} />
                    <Badge tone="muted">{humanise(c.kind)}</Badge>
                    <span className="text-xs text-ink-subtle">
                      raised by {c.raised_by.display_name} ({c.raised_by.kind}) · iteration {c.iteration} · {formatDateTime(c.created_at)}
                    </span>
                  </div>
                  <p className="mt-1 text-[13px]">{c.argument}</p>
                  <p className="mt-0.5 text-xs text-ink-muted">
                    Target ({c.target_type}):{" "}
                    {claim ? (
                      <LinkButton onClick={() => openClaim(claim.id)}>{claim.statement}</LinkButton>
                    ) : (
                      (hyp?.statement ?? c.target_id)
                    )}
                  </p>
                  {c.research_question && <p className="mt-0.5 text-xs text-ink-muted">Research question: {c.research_question}</p>}
                  <p className="mt-0.5 text-xs text-ink-muted">
                    Follow-up research {c.research_attempted ? "attempted" : "not attempted"}
                  </p>
                  {c.resolution_note && <p className="mt-1 rounded bg-surface-muted px-2 py-1 text-xs">Resolution: {c.resolution_note}</p>}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
