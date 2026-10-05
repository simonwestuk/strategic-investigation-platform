"use client";

import { optionChain } from "@/lib/decision-room";
import { formatDateTime, humanise } from "@/lib/format";
import type { StrategicOption } from "@/lib/types";
import { Badge, type Tone } from "../../ui/Badge";
import { LinkButton } from "../../ui/Button";
import { ClassificationBadge } from "../../ui/ClassificationBadge";
import { ConfidenceMeter } from "../../ui/ConfidenceMeter";
import { BulletList, EmptyState, Eyebrow, Panel } from "../../ui/Panel";
import { AiRecommendationLabel, OptionReviewBadge, SyntheticBadge } from "../../ui/StatusBadges";
import { FreshnessBadge, TierBadge } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

const LEVEL_TONE: Record<string, Tone> = { high: "warn", medium: "muted", low: "muted" };

function EvidenceChain({ option }: { option: StrategicOption }) {
  const { lookups, openClaim, openSource } = useWorkspace();
  const chain = optionChain(option, lookups);
  const claimLinks = [...chain.findings.flatMap((f) => f.claims), ...chain.directClaims];
  if (chain.findings.length === 0 && chain.directClaims.length === 0) {
    return <p className="text-[13px] text-ink-subtle">No findings or claims cited — this option rests on the absence of evidence.</p>;
  }
  return (
    <ol className="space-y-3" aria-label="Evidence chain">
      {chain.findings.map(({ finding, claims }) => (
        <li key={finding.id} className="rounded border border-line">
          <div className="border-b border-line bg-surface-muted px-3 py-1.5 text-xs">
            <span className="font-semibold text-ink">Finding</span> · {humanise(finding.status)} ·{" "}
            <span className="text-ink-muted">{finding.statement}</span>
          </div>
          <ul className="space-y-2 px-3 py-2">
            {claims.map((cl) => (
              <ChainClaim key={cl.claim.id} link={cl} openClaim={openClaim} openSource={openSource} />
            ))}
          </ul>
        </li>
      ))}
      {chain.directClaims.length > 0 && (
        <li className="rounded border border-line px-3 py-2">
          <p className="mb-1 text-xs font-semibold">Claims cited directly</p>
          <ul className="space-y-2">
            {chain.directClaims.map((cl) => (
              <ChainClaim key={cl.claim.id} link={cl} openClaim={openClaim} openSource={openSource} />
            ))}
          </ul>
        </li>
      )}
      <li className="text-xs text-ink-subtle">
        {claimLinks.length} claim(s), {claimLinks.reduce((n, c) => n + c.evidence.length, 0)} evidence item(s). Open a claim for its
        full confidence assessment.
      </li>
    </ol>
  );
}

function ChainClaim({
  link,
  openClaim,
  openSource,
}: {
  link: ReturnType<typeof optionChain>["directClaims"][number];
  openClaim: (id: string) => void;
  openSource: (id: string) => void;
}) {
  const { claim, evidence } = link;
  return (
    <li className="text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold text-ink-subtle">Claim</span>
        <ClassificationBadge classification={claim.classification} proposed={claim.proposed_classification} />
        {claim.confidence && <ConfidenceMeter band={claim.confidence.band} score={claim.confidence.score} />}
      </div>
      <LinkButton onClick={() => openClaim(claim.id)} className="mt-0.5 leading-snug">
        {claim.statement}
      </LinkButton>
      {evidence.length > 0 && (
        <ul className="mt-1.5 space-y-1 border-l-2 border-line pl-3">
          {evidence.map(({ evidence: e, source, stance }) => (
            <li key={e.id} className="text-xs">
              <span className="flex flex-wrap items-center gap-1">
                <span className="font-semibold text-ink-subtle">Evidence</span>
                <Badge tone={stance === "supports" ? "ok" : "danger"}>{stance}</Badge>
                {e.quality && <TierBadge tier={e.quality.tier} />}
                {e.quality && <FreshnessBadge freshness={e.quality.freshness} />}
                <span className="text-ink">{e.statement}</span>
              </span>
              {source && (
                <span className="mt-0.5 flex flex-wrap items-center gap-1 pl-2 text-ink-muted">
                  <span aria-hidden="true">↳</span> Source:
                  <LinkButton onClick={() => openSource(source.id)}>{source.title}</LinkButton>
                  {source.synthetic && <SyntheticBadge />}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function OptionCard({ option, open }: { option: StrategicOption; open: boolean }) {
  return (
    <details open={open} className="group rounded-md border border-dashed border-ai-line bg-surface">
      <summary className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3">
        <span className="chevron mt-0.5 text-ink-subtle" aria-hidden="true">
          ›
        </span>
        <span className="min-w-0 flex-1">
          <span className="mb-1 flex flex-wrap items-center gap-1.5">
            <AiRecommendationLabel />
            <OptionReviewBadge status={option.review_status} />
          </span>
          <span className="block text-[14px] font-semibold text-ink">{option.title}</span>
          <span className="block text-[13px] text-ink-muted">{option.description}</span>
        </span>
        <span className="flex flex-wrap items-center gap-1.5">
          <ConfidenceMeter band={option.confidence_band} />
          <Badge tone={LEVEL_TONE[option.consequence]}>{humanise(option.consequence)} consequence</Badge>
          <Badge tone={option.reversibility === "low" ? "warn" : "muted"}>{humanise(option.reversibility)} reversibility</Badge>
        </span>
      </summary>
      <div className="space-y-4 border-t border-line px-4 py-3">
        <p className="text-[13px]">
          <span className="font-medium">Rationale: </span>
          {option.rationale}
        </p>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <Eyebrow className="mb-1">Expected benefits</Eyebrow>
            <BulletList items={option.expected_benefits} empty="None stated." />
          </div>
          <div>
            <Eyebrow className="mb-1">Risks</Eyebrow>
            <BulletList items={option.risks} empty="None stated." />
          </div>
          <div>
            <Eyebrow className="mb-1">Uncertainties</Eyebrow>
            <BulletList items={option.uncertainties} empty="None stated." />
          </div>
          <div>
            <Eyebrow className="mb-1">Dependencies</Eyebrow>
            <BulletList items={option.dependencies} empty="None stated." />
          </div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <p className="text-[13px]">
            <span className="font-medium">Reversibility ({option.reversibility}): </span>
            {option.reversibility_note || "—"}
          </p>
          {option.additional_evidence_needed.length > 0 && (
            <div>
              <Eyebrow className="mb-1">Additional evidence needed</Eyebrow>
              <BulletList items={option.additional_evidence_needed} />
            </div>
          )}
        </div>
        {option.reviewer_note && (
          <p className="rounded bg-accent-soft px-3 py-1.5 text-[13px] text-ink">
            <span className="font-medium">Reviewer note: </span>
            {option.reviewer_note}
          </p>
        )}
        <div>
          <Eyebrow className="mb-2">Evidence chain: option → finding → claim → evidence → source</Eyebrow>
          <EvidenceChain option={option} />
        </div>
        <p className="text-xs text-ink-subtle">
          Generated by {option.created_by.display_name} ({option.created_by.kind}) on {formatDateTime(option.created_at)} ·{" "}
          {option.id}
        </p>
      </div>
    </details>
  );
}

export function OptionsPanel() {
  const { detail } = useWorkspace();
  const options = detail.options;
  return (
    <Panel
      title="Strategic options"
      subtitle="AI recommendations generated from accepted findings. They are inputs to a human decision, never decisions themselves."
      actions={<AiRecommendationLabel />}
    >
      {options.length === 0 ? (
        <EmptyState>No options have been generated yet.</EmptyState>
      ) : (
        <div className="space-y-2">
          {options.map((o, i) => (
            <OptionCard key={o.id} option={o} open={i === 0} />
          ))}
        </div>
      )}
    </Panel>
  );
}
