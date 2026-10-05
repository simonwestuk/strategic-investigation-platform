"use client";

import clsx from "clsx";
import { type CausalDriver, type SegmentFinding, type SegmentVerdict, deriveCausalPicture } from "@/lib/causal";
import { humanise } from "@/lib/format";
import { Badge } from "../../ui/Badge";
import { EmptyState, Eyebrow, Panel } from "../../ui/Panel";
import { useWorkspace } from "../WorkspaceContext";

const VERDICT_CELL: Record<SegmentVerdict, { glyph: string; label: string; cls: string }> = {
  supported: { glyph: "✓", label: "Applies", cls: "bg-ok-bg text-ok-fg" },
  rejected: { glyph: "✕", label: "Rejected", cls: "bg-danger-bg text-danger-fg" },
  weakened: { glyph: "↘", label: "Weakened", cls: "bg-warn-bg text-warn-fg" },
  open: { glyph: "?", label: "Unresolved", cls: "border border-dashed border-unknown-line text-unknown-fg" },
};

function SegmentChip({ f }: { f: SegmentFinding }) {
  const { detail } = useWorkspace();
  const v = VERDICT_CELL[f.verdict];
  return (
    <span title={`${f.statement}\n${f.reason}`} className={clsx("inline-flex items-center gap-1 rounded px-1.5 py-px text-[11px] font-medium", v.cls)}>
      <span aria-hidden="true">{v.glyph}</span>
      {detail.segment_names?.[f.segment] ?? f.segment}
      <span className="sr-only">: {v.label}</span>
    </span>
  );
}

function DriverItem({ d }: { d: CausalDriver }) {
  const scope =
    d.verdict === "mixed"
      ? "Segment-specific"
      : d.segmented
        ? `${humanise(d.verdict)} in every segment tested`
        : d.verdict === "supported"
          ? "Portfolio-wide"
          : d.verdict === "open"
            ? "Not resolved"
            : humanise(d.verdict);
  return (
    <li className="rounded border border-line bg-surface px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-semibold">{humanise(d.category)}</span>
        <Badge tone={d.verdict === "mixed" ? "accent" : "muted"}>{scope}</Badge>
      </div>
      <p className="mt-0.5 line-clamp-2 text-xs leading-snug text-ink-muted" title={d.hypothesis.statement}>
        {d.hypothesis.statement}
      </p>
      {d.segmented && (
        <div className="mt-1.5 space-y-1 text-[11px]">
          {d.appliesIn.length > 0 && (
            <div className="flex flex-wrap items-center gap-1">
              <span className="w-16 text-ink-subtle">Applies in</span>
              {d.appliesIn.map((f) => (
                <SegmentChip key={f.hypothesisId} f={f} />
              ))}
            </div>
          )}
          {(d.rejectedIn.length > 0 || d.weakenedIn.length > 0) && (
            <div className="flex flex-wrap items-center gap-1">
              <span className="w-16 text-ink-subtle">Rejected in</span>
              {[...d.rejectedIn, ...d.weakenedIn].map((f) => (
                <SegmentChip key={f.hypothesisId} f={f} />
              ))}
            </div>
          )}
          {d.openIn.length > 0 && (
            <div className="flex flex-wrap items-center gap-1">
              <span className="w-16 text-ink-subtle">Open in</span>
              {d.openIn.map((f) => (
                <SegmentChip key={f.hypothesisId} f={f} />
              ))}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function CausalPicturePanel() {
  const { detail, goTo } = useWorkspace();
  const picture = deriveCausalPicture(detail.hypotheses);
  // Segment-specific drivers first: they carry the most decision-relevant nuance.
  const supported = [...picture.supported].sort((a, b) => Number(b.segmented) - Number(a.segmented));
  const segmented = [...picture.supported, ...picture.rejected, ...picture.open].filter((d) => d.segmented);

  return (
    <Panel
      title="Likely causal picture"
      subtitle="Derived from the hypothesis tree. Where evidence diverged by segment, a driver is split to show where it applies and where it was rejected."
      actions={
        <button type="button" className="text-xs text-accent hover:underline" onClick={() => goTo("hypotheses")}>
          Open hypothesis map →
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-3">
        <div>
          <Eyebrow className="mb-2">Supported drivers ({picture.supported.length})</Eyebrow>
          {supported.length ? (
            <ul className="space-y-2">{supported.map((d) => <DriverItem key={d.hypothesis.id} d={d} />)}</ul>
          ) : (
            <EmptyState>No driver is supported yet.</EmptyState>
          )}
        </div>
        <div>
          <Eyebrow className="mb-2">Rejected or weakened ({picture.rejected.length})</Eyebrow>
          {picture.rejected.length ? (
            <ul className="space-y-2">{picture.rejected.map((d) => <DriverItem key={d.hypothesis.id} d={d} />)}</ul>
          ) : (
            <EmptyState>No driver has been rejected.</EmptyState>
          )}
        </div>
        <div>
          <Eyebrow className="mb-2">Unresolved ({picture.open.length})</Eyebrow>
          {picture.open.length ? (
            <ul className="space-y-2">{picture.open.map((d) => <DriverItem key={d.hypothesis.id} d={d} />)}</ul>
          ) : (
            <EmptyState>Every driver has been tested.</EmptyState>
          )}
        </div>
      </div>

      {segmented.length > 0 && picture.segments.length > 0 && (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[520px] border-collapse text-left text-[13px]">
            <caption className="mb-2 text-left text-xs text-ink-muted">
              Driver × segment: where each split driver applies (✓), was rejected (✕) or remains unresolved (?).
            </caption>
            <thead>
              <tr className="border-b border-line text-xs text-ink-muted">
                <th scope="col" className="py-1.5 pr-3 font-medium">
                  Driver
                </th>
                {picture.segments.map((s) => (
                  <th key={s} scope="col" title={s} className="px-2 py-1.5 text-center font-medium">
                    {detail.segment_names?.[s] ?? s}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {segmented.map((d) => {
                const all = [...d.appliesIn, ...d.rejectedIn, ...d.weakenedIn, ...d.openIn];
                return (
                  <tr key={d.hypothesis.id} className="border-b border-line last:border-0">
                    <th scope="row" className="py-1.5 pr-3 font-medium">
                      {humanise(d.category)}
                    </th>
                    {picture.segments.map((s) => {
                      const f = all.find((x) => x.segment === s);
                      if (!f)
                        return (
                          <td key={s} className="px-2 py-1.5 text-center text-xs text-ink-subtle">
                            <span aria-label="not tested">—</span>
                          </td>
                        );
                      const v = VERDICT_CELL[f.verdict];
                      return (
                        <td key={s} className="px-2 py-1.5 text-center">
                          <span title={f.statement} className={clsx("inline-flex min-w-20 justify-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium", v.cls)}>
                            <span aria-hidden="true">{v.glyph}</span> {v.label}
                          </span>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
