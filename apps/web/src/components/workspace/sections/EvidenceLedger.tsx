"use client";

import { useMemo, useState } from "react";
import {
  DEFAULT_EVIDENCE_FILTER,
  type EvidenceFilter,
  FRESHNESS_ORDER,
  TIER_ORDER,
  evidenceFlags,
  filterEvidence,
} from "@/lib/evidence";
import { formatDate, formatDateTime, humanise } from "@/lib/format";
import { Badge } from "../../ui/Badge";
import { Button, LinkButton, inputClass } from "../../ui/Button";
import { EmptyState, SectionHeading } from "../../ui/Panel";
import { SyntheticBadge } from "../../ui/StatusBadges";
import { ClassificationTags } from "../ScanSummary";
import { FlagBadges, FreshnessBadge, TierBadge, VerificationBadge } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

function Select<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: readonly (readonly [T, string])[];
  onChange: (v: T) => void;
}) {
  return (
    <label className="flex flex-col text-xs text-ink-muted">
      {label}
      <select className={`${inputClass} mt-0.5 py-1`} value={value} onChange={(e) => onChange(e.target.value as T)}>
        {options.map(([v, l]) => (
          <option key={v} value={v}>
            {l}
          </option>
        ))}
      </select>
    </label>
  );
}

const all = ["all", "All"] as const;

export function EvidenceLedger() {
  const { detail, lookups, openSource } = useWorkspace();
  const [f, setF] = useState<EvidenceFilter>(DEFAULT_EVIDENCE_FILTER);
  const set = <K extends keyof EvidenceFilter>(k: K, v: EvidenceFilter[K]) => setF((x) => ({ ...x, [k]: v }));
  const rows = useMemo(() => filterEvidence(detail.evidence, lookups.sources, f), [detail.evidence, lookups.sources, f]);
  const allFlags = [...new Set(detail.evidence.flatMap((e) => evidenceFlags(e, lookups.sources.get(e.source_id))))];
  const kinds = [...new Set(detail.evidence.map((e) => e.kind))];

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Evidence ledger"
        description="Every evidence item with its authority tier (for the kind of evidence needed), freshness relative to the as-of date, quote verification and flags — and the source it came from."
      />
      <div className="grid grid-cols-2 gap-2 rounded-md border border-line bg-surface p-3 sm:grid-cols-4 xl:grid-cols-8">
        <label className="col-span-2 flex flex-col text-xs text-ink-muted">
          Search
          <input
            className={`${inputClass} mt-0.5 py-1`}
            value={f.text}
            placeholder="Statement, quote, source, segment"
            onChange={(e) => set("text", e.target.value)}
          />
        </label>
        <Select label="Kind" value={f.kind} onChange={(v) => set("kind", v)} options={[all, ...kinds.map((k) => [k, humanise(k)] as const)]} />
        <Select label="Authority tier" value={f.tier} onChange={(v) => set("tier", v)} options={[all, ...TIER_ORDER.map((t) => [t, humanise(t)] as const)]} />
        <Select
          label="Freshness"
          value={f.freshness}
          onChange={(v) => set("freshness", v)}
          options={[all, ...FRESHNESS_ORDER.map((t) => [t, humanise(t)] as const)]}
        />
        <Select
          label="Verification"
          value={f.verification}
          onChange={(v) => set("verification", v)}
          options={[all, ["verified", "Verified quote"], ["computed", "Computed"], ["not_found", "Quote not found"]]}
        />
        <Select
          label="Flags"
          value={f.flag}
          onChange={(v) => set("flag", v)}
          options={[all, ["any", "Any flag"], ["none", "No flags"], ...allFlags.map((x) => [x, humanise(x)] as const)]}
        />
        <Select
          label="Source origin"
          value={f.origin}
          onChange={(v) => set("origin", v)}
          options={[all, ["external_web", "External web"], ["internal", "Internal"], ["human", "Human-supplied"]]}
        />
      </div>
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>
          Showing {rows.length} of {detail.evidence.length} evidence items
        </span>
        <Button variant="ghost" onClick={() => setF(DEFAULT_EVIDENCE_FILTER)}>
          Reset filters
        </Button>
      </div>

      {rows.length === 0 ? (
        <EmptyState>No evidence matches these filters.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full min-w-[960px] text-left text-[13px]">
            <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-1.5 font-medium">Evidence</th>
                <th className="px-3 py-1.5 font-medium">Kind / need</th>
                <th className="px-3 py-1.5 font-medium">Quality</th>
                <th className="px-3 py-1.5 font-medium">Source</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => {
                const src = lookups.sources.get(e.source_id);
                const flags = evidenceFlags(e, src);
                return (
                  <tr key={e.id} className="border-b border-line align-top last:border-0">
                    <td className="max-w-[460px] px-3 py-2">
                      <p>{e.statement}</p>
                      {e.quote && <p className="mt-0.5 text-xs italic text-ink-muted">“{e.quote}”</p>}
                      <p className="mt-0.5 flex flex-wrap gap-1 text-[11px] text-ink-subtle">
                        <span className="font-mono">{e.id}</span>
                        {e.segments.length > 0 && <span>· segments {e.segments.join(", ")}</span>}
                        {e.links.map((l) => (
                          <span key={l.hypothesis_id} className={l.stance === "contradicts" ? "text-danger-fg" : undefined}>
                            · {l.stance} {lookups.hypotheses.get(l.hypothesis_id)?.category ?? l.hypothesis_id}
                          </span>
                        ))}
                      </p>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col items-start gap-1">
                        <Badge tone="muted">{humanise(e.kind)}</Badge>
                        <span className="text-xs text-ink-muted">{humanise(e.need)}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col items-start gap-1">
                        {e.quality ? <TierBadge tier={e.quality.tier} /> : <Badge tone="muted">Unassessed</Badge>}
                        {e.quality && <FreshnessBadge freshness={e.quality.freshness} ageDays={e.quality.age_days} />}
                        <VerificationBadge verification={e.verification} />
                        <FlagBadges flags={flags} />
                      </div>
                    </td>
                    <td className="max-w-[300px] px-3 py-2">
                      {src ? (
                        <div className="space-y-0.5">
                          <LinkButton onClick={() => openSource(src.id)}>{src.title}</LinkButton>
                          <p className="text-xs text-ink-muted">
                            {src.publisher ?? src.domain ?? "—"} · {humanise(src.source_type)}
                          </p>
                          <div className="flex flex-wrap gap-1">{src.synthetic && <SyntheticBadge />}</div>
                        </div>
                      ) : (
                        <span className="text-xs text-ink-subtle">{e.source_id}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <section>
        <h3 className="mb-2 text-[14px] font-semibold">Source provenance ({detail.sources.length})</h3>
        <div className="overflow-x-auto rounded-md border border-line bg-surface">
          <table className="w-full min-w-[1000px] text-left text-[13px]">
            <thead className="border-b border-line bg-surface-muted text-xs text-ink-muted">
              <tr>
                <th className="px-3 py-1.5 font-medium">Source</th>
                <th className="px-3 py-1.5 font-medium">Type</th>
                <th className="px-3 py-1.5 font-medium">Published / updated</th>
                <th className="px-3 py-1.5 font-medium">Retrieved</th>
                <th className="px-3 py-1.5 font-medium">Classification</th>
                <th className="px-3 py-1.5 font-medium">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {detail.sources.map((s) => (
                <tr key={s.id} className="border-b border-line align-top last:border-0">
                  <td className="max-w-[340px] px-3 py-2">
                    <LinkButton onClick={() => openSource(s.id)}>{s.title}</LinkButton>
                    <p className="text-xs text-ink-muted">{s.publisher ?? "—"}</p>
                    {s.canonical_url && <p className="truncate font-mono text-[11px] text-ink-subtle">{s.canonical_url}</p>}
                    <div className="mt-0.5 flex flex-wrap gap-1">
                      {s.synthetic && <SyntheticBadge />}
                      {s.injection_flags.length > 0 && <FlagBadges flags={["injection_suspected"]} />}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {humanise(s.source_type)}
                    <p className="text-ink-subtle">{humanise(s.origin)}</p>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-xs">
                    {formatDate(s.published_on)}
                    <p className="text-ink-subtle">{s.updated_on ? `upd. ${formatDate(s.updated_on)}` : "not updated"}</p>
                  </td>
                  <td className="px-3 py-2 text-xs">
                    {formatDateTime(s.retrieved_at)}
                    <p className="text-ink-subtle">
                      {humanise(s.retrieval_method)}
                      {s.retrieval_provider ? ` via ${s.retrieval_provider}` : ""}
                    </p>
                  </td>
                  <td className="px-3 py-2">
                    <ClassificationTags c={s.classification} />
                  </td>
                  <td className="px-3 py-2 text-xs tabular-nums">{detail.evidence.filter((e) => e.source_id === s.id).length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
