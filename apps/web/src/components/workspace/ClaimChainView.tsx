import type { ReactNode } from "react";
import { CLASSIFICATION_META, CONFIDENCE_LABELS } from "@/lib/labels";
import { formatDateTime, humanise } from "@/lib/format";
import type { ClaimChain, Evidence, Hypothesis } from "@/lib/types";
import { Badge } from "../ui/Badge";
import { ClassificationBadge } from "../ui/ClassificationBadge";
import { ConfidenceMeter } from "../ui/ConfidenceMeter";
import { BulletList, EmptyState, Eyebrow } from "../ui/Panel";
import {
  AiRecommendationLabel,
  ChallengeStatusBadge,
  OptionReviewBadge,
  SeverityBadge,
} from "../ui/StatusBadges";
import { EvidenceCard } from "./refs";

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line pt-3">
      <Eyebrow className="mb-2">{title}</Eyebrow>
      {children}
    </section>
  );
}

/**
 * Full provenance chain for one claim: classification and why, the confidence rubric, the
 * reasoning, then evidence → source, and what the claim feeds (findings, options) or faces
 * (challenges, human override).
 */
export function ClaimChainView({
  chain,
  onOpenSource,
  hypotheses,
}: {
  chain: ClaimChain;
  onOpenSource: (sourceId: string) => void;
  hypotheses?: ReadonlyMap<string, Hypothesis>;
}) {
  const { claim } = chain;
  const conf = claim.confidence;
  const sources = new Map(chain.sources.map((s) => [s.id, s]));
  const evidence = new Map(chain.evidence.map((e) => [e.id, e]));
  const pick = (ids: string[]) => ids.map((id) => evidence.get(id)).filter((e): e is Evidence => Boolean(e));
  const supporting = pick(claim.supporting_evidence_ids);
  const contradicting = pick(claim.contradicting_evidence_ids);
  const capped = claim.proposed_classification !== claim.classification;

  return (
    <div className="space-y-4" data-testid="claim-chain">
      <div>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <ClassificationBadge classification={claim.classification} size="md" />
          {conf && <ConfidenceMeter band={conf.band} score={conf.score} />}
          {claim.causal && <Badge tone="muted">Causal claim</Badge>}
          <Badge tone="muted">Review: {humanise(claim.review_state)}</Badge>
          {!claim.active && <Badge tone="warn">Superseded</Badge>}
        </div>
        <p data-testid="claim-statement" className="text-[15px] leading-snug text-ink">{claim.statement}</p>
        <p className="mt-1 text-xs text-ink-subtle">
          {claim.id} · classified by {claim.created_by.display_name} ({claim.created_by.kind}) · iteration {claim.iteration} ·
          updated {formatDateTime(claim.updated_at)}
        </p>
      </div>

      <Block title="Classification">
        <div className="grid gap-2 text-[13px] sm:grid-cols-2">
          <div className="rounded border border-line px-3 py-2">
            <p className="text-xs text-ink-muted">Proposed by analyst</p>
            <ClassificationBadge classification={claim.proposed_classification} />
          </div>
          <div className="rounded border border-line px-3 py-2">
            <p className="text-xs text-ink-muted">Final (after rubric{claim.human_override ? " and human override" : ""})</p>
            <ClassificationBadge classification={claim.classification} />
          </div>
        </div>
        {capped && !claim.human_override && (
          <p className="mt-2 rounded bg-warn-bg px-3 py-2 text-[13px] text-warn-fg" role="note">
            The deterministic confidence rubric downgraded this claim from{" "}
            <strong>{CLASSIFICATION_META[claim.proposed_classification].label}</strong> to{" "}
            <strong>{CLASSIFICATION_META[claim.classification].label}</strong>. See the ceiling reasons below.
          </p>
        )}
      </Block>

      {conf && (
        <Block title="Confidence assessment (deterministic rubric)">
          <p className="mb-2 text-[13px]">
            <strong>{CONFIDENCE_LABELS[conf.band]}</strong> confidence · score {conf.score} · classification ceiling{" "}
            <ClassificationBadge classification={conf.classification_ceiling} />
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <p className="mb-1 text-xs font-medium text-ink-muted">Scoring factors</p>
              <ul className="space-y-0.5 font-mono text-[12px] text-ink">
                {conf.factors.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium text-ink-muted">Ceiling reasons</p>
              <BulletList items={conf.ceiling_reasons} empty="No ceiling applied." />
            </div>
          </div>
        </Block>
      )}

      <Block title="Reasoning">
        <div className="space-y-2 text-[13px]">
          <p>{claim.reasoning_summary}</p>
          {claim.inferential_step && (
            <p>
              <span className="font-medium">Inferential step: </span>
              {claim.inferential_step}
            </p>
          )}
          <p className="text-ink-muted">{claim.source_quality_summary}</p>
          {claim.related_hypothesis_ids.length > 0 && (
            <p className="text-ink-muted">
              Tests hypothesis:{" "}
              {claim.related_hypothesis_ids.map((h) => hypotheses?.get(h)?.statement ?? h).join("; ")}
            </p>
          )}
        </div>
      </Block>

      <Block title="Limitations and gaps">
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <p className="mb-1 text-xs font-medium text-ink-muted">Limitations</p>
            <BulletList items={claim.limitations} empty="None recorded." />
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-ink-muted">Missing evidence</p>
            <BulletList items={claim.missing_evidence} empty="None recorded." />
          </div>
        </div>
        {claim.next_question && (
          <p className="mt-2 text-[13px]">
            <span className="font-medium">Next question: </span>
            {claim.next_question}
          </p>
        )}
      </Block>

      <Block title={`Supporting evidence (${supporting.length})`}>
        {supporting.length === 0 ? (
          <EmptyState>No supporting evidence.</EmptyState>
        ) : (
          <div className="space-y-2">
            {supporting.map((e) => (
              <EvidenceCard key={e.id} evidence={e} source={sources.get(e.source_id)} stance="supports" onOpenSource={onOpenSource} />
            ))}
          </div>
        )}
      </Block>

      <Block title={`Contradicting evidence (${contradicting.length})`}>
        {contradicting.length === 0 ? (
          <EmptyState>No contradicting evidence recorded.</EmptyState>
        ) : (
          <div className="space-y-2">
            {contradicting.map((e) => (
              <EvidenceCard key={e.id} evidence={e} source={sources.get(e.source_id)} stance="contradicts" onOpenSource={onOpenSource} />
            ))}
          </div>
        )}
      </Block>

      <Block title={`Findings built on this claim (${chain.findings.length})`}>
        {chain.findings.length === 0 ? (
          <EmptyState>Not used in any finding.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {chain.findings.map((f) => (
              <li key={f.id} className="rounded border border-line px-3 py-2 text-[13px]">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <ClassificationBadge classification={f.classification} />
                  <ConfidenceMeter band={f.confidence_band} />
                  <Badge tone="muted">Finding · {humanise(f.status)}</Badge>
                </div>
                <p>{f.statement}</p>
                {f.criteria_met.length > 0 && (
                  <details className="mt-1 text-xs text-ink-muted">
                    <summary>Criteria met ({f.criteria_met.length})</summary>
                    <BulletList items={f.criteria_met} />
                  </details>
                )}
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title={`Strategic options citing it (${chain.options.length})`}>
        {chain.options.length === 0 ? (
          <EmptyState>No option relies on this claim.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {chain.options.map((o) => (
              <li key={o.id} className="rounded border border-dashed border-ai-line px-3 py-2 text-[13px]">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <AiRecommendationLabel />
                  <OptionReviewBadge status={o.review_status} />
                </div>
                <p className="font-medium">{o.title}</p>
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title={`Challenges (${chain.challenges.length})`}>
        {chain.challenges.length === 0 ? (
          <EmptyState>No challenges raised against this claim.</EmptyState>
        ) : (
          <ul className="space-y-2">
            {chain.challenges.map((c) => (
              <li key={c.id} className="rounded border border-line px-3 py-2 text-[13px]">
                <div className="mb-1 flex flex-wrap items-center gap-2">
                  <Badge tone="muted">{humanise(c.kind)}</Badge>
                  <SeverityBadge severity={c.severity} />
                  <ChallengeStatusBadge status={c.status} />
                  <span className="text-xs text-ink-subtle">raised by {c.raised_by.display_name}</span>
                </div>
                <p>{c.argument}</p>
                {c.resolution_note && <p className="mt-1 text-xs text-ink-muted">Resolution: {c.resolution_note}</p>}
              </li>
            ))}
          </ul>
        )}
      </Block>

      <Block title="Human override">
        {claim.human_override ? (
          <div className="rounded border border-accent/40 bg-accent-soft px-3 py-2 text-[13px]">
            <p>
              <strong>{claim.human_override.actor.display_name}</strong> changed the classification from{" "}
              <ClassificationBadge classification={claim.human_override.previous} /> to{" "}
              <ClassificationBadge classification={claim.human_override.new} /> on {formatDateTime(claim.human_override.at)}.
            </p>
            <p className="mt-1">Reason: {claim.human_override.reason}</p>
          </div>
        ) : (
          <p className="text-[13px] text-ink-subtle">No human override. Reviewers can override a classification from any review form.</p>
        )}
      </Block>
    </div>
  );
}
