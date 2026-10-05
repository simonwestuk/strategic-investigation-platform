"use client";

import clsx from "clsx";
import { evidenceFlags } from "@/lib/evidence";
import { formatDate, humanise } from "@/lib/format";
import type { Claim, Evidence, Source } from "@/lib/types";
import { Badge, type Tone } from "../ui/Badge";
import { LinkButton } from "../ui/Button";
import { ClassificationBadge } from "../ui/ClassificationBadge";
import { ConfidenceMeter } from "../ui/ConfidenceMeter";
import { SyntheticBadge } from "../ui/StatusBadges";

const TIER_TONE: Record<string, Tone> = { primary: "ok", secondary: "info", tertiary: "warn", unsuitable: "danger" };
const FRESH_TONE: Record<string, Tone> = { current: "ok", ageing: "warn", stale: "danger", undated: "muted" };
const VERIFY_TONE: Record<string, Tone> = { verified: "ok", computed: "info", not_found: "danger" };

export function TierBadge({ tier }: { tier: string }) {
  return (
    <Badge tone={TIER_TONE[tier] ?? "neutral"} title="Authority tier for this kind of evidence">
      {humanise(tier)} tier
    </Badge>
  );
}

export function FreshnessBadge({ freshness, ageDays }: { freshness: string; ageDays?: number | null }) {
  return (
    <Badge tone={FRESH_TONE[freshness] ?? "neutral"} title={ageDays != null ? `${ageDays} days before as-of date` : undefined}>
      {humanise(freshness)}
      {ageDays != null && <span className="font-normal opacity-80">· {ageDays}d</span>}
    </Badge>
  );
}

export function VerificationBadge({ verification }: { verification: string }) {
  const text =
    verification === "verified" ? "Quote verified" : verification === "computed" ? "Computed from data" : "Quote not found";
  return <Badge tone={VERIFY_TONE[verification] ?? "neutral"}>{text}</Badge>;
}

export function FlagBadges({ flags }: { flags: readonly string[] }) {
  return (
    <>
      {flags.map((f) => (
        <Badge key={f} tone={f === "injection_suspected" ? "danger" : "warn"}>
          ⚑ {humanise(f)}
        </Badge>
      ))}
    </>
  );
}

/** Clickable claim reference: classification + statement, opens the claim chain drawer. */
export function ClaimRef({
  claim,
  onOpen,
  showConfidence = true,
  className,
}: {
  claim: Claim;
  onOpen: (id: string) => void;
  showConfidence?: boolean;
  className?: string;
}) {
  return (
    <div className={clsx("flex flex-col gap-1", className)}>
      <div className="flex flex-wrap items-center gap-2">
        <ClassificationBadge classification={claim.classification} proposed={claim.proposed_classification} />
        {showConfidence && claim.confidence && <ConfidenceMeter band={claim.confidence.band} score={claim.confidence.score} />}
        {claim.human_override && <Badge tone="accent">Human override</Badge>}
      </div>
      <LinkButton onClick={() => onOpen(claim.id)} className="text-[13px] leading-snug">
        {claim.statement}
      </LinkButton>
    </div>
  );
}

export function SourceLine({ source, onOpen }: { source: Source | undefined; onOpen: (id: string) => void }) {
  if (!source) return <span className="text-xs text-ink-subtle">Source unavailable</span>;
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5 text-xs">
      <LinkButton onClick={() => onOpen(source.id)}>{source.title}</LinkButton>
      <span className="text-ink-subtle">
        {source.publisher ?? source.domain ?? humanise(source.origin)} · {humanise(source.source_type)}
        {source.published_on && ` · published ${formatDate(source.published_on)}`}
      </span>
      {source.synthetic && <SyntheticBadge />}
      {source.injection_flags.length > 0 && <FlagBadges flags={["injection_suspected"]} />}
    </span>
  );
}

/** An evidence item with its quality signals and the source it came from. */
export function EvidenceCard({
  evidence,
  source,
  stance,
  onOpenSource,
}: {
  evidence: Evidence;
  source: Source | undefined;
  stance?: "supports" | "contradicts";
  onOpenSource: (id: string) => void;
}) {
  const flags = evidenceFlags(evidence, source);
  return (
    <div
      className={clsx(
        "rounded border bg-surface px-3 py-2",
        stance === "contradicts" ? "border-danger-fg/40" : "border-line",
      )}
    >
      <div className="mb-1 flex flex-wrap items-center gap-1.5">
        {stance && (
          <Badge tone={stance === "supports" ? "ok" : "danger"}>{stance === "supports" ? "Supports" : "Contradicts"}</Badge>
        )}
        <Badge tone="muted">{humanise(evidence.kind)}</Badge>
        {evidence.quality && <TierBadge tier={evidence.quality.tier} />}
        {evidence.quality && <FreshnessBadge freshness={evidence.quality.freshness} ageDays={evidence.quality.age_days} />}
        <VerificationBadge verification={evidence.verification} />
        <FlagBadges flags={flags} />
        <span className="ml-auto font-mono text-[10.5px] text-ink-subtle">{evidence.id}</span>
      </div>
      <p className="text-[13px] text-ink">{evidence.statement}</p>
      {evidence.quote && (
        <blockquote className="mt-1 border-l-2 border-line-strong pl-2 text-[12.5px] italic text-ink-muted">
          “{evidence.quote}”
        </blockquote>
      )}
      {evidence.locator && <p className="mt-1 font-mono text-[11px] text-ink-subtle">{evidence.locator}</p>}
      {evidence.quality?.rationale && <p className="mt-1 text-xs text-ink-muted">{evidence.quality.rationale}</p>}
      <div className="mt-1.5">
        <SourceLine source={source} onOpen={onOpenSource} />
      </div>
    </div>
  );
}
