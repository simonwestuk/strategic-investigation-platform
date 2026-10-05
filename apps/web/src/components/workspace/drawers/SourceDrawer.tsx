"use client";

import { api } from "@/lib/api";
import { formatDate, formatDateTime, humanise } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { ErrorNotice } from "../../ErrorNotice";
import { Badge } from "../../ui/Badge";
import { Drawer } from "../../ui/Drawer";
import { EmptyState, Eyebrow, KeyValues, Mono } from "../../ui/Panel";
import { SyntheticBadge } from "../../ui/StatusBadges";
import { EvidenceCard, FlagBadges } from "../refs";
import { useWorkspace } from "../WorkspaceContext";

export function SourceDrawer({ sourceId, onClose, onBack }: { sourceId: string | null; onClose: () => void; onBack?: () => void }) {
  const { detail, lookups, openSource } = useWorkspace();
  const res = useAsync(
    () => (sourceId ? api.getSource(detail.summary.id, sourceId) : Promise.resolve(null)),
    [sourceId, detail.summary.id],
  );
  const s = res.data && res.data.id === sourceId ? res.data : null;
  const fallback = sourceId ? lookups.sources.get(sourceId) : undefined;
  const title = s?.title ?? fallback?.title ?? "Source";
  const derived = sourceId ? detail.evidence.filter((e) => e.source_id === sourceId) : [];

  return (
    <Drawer
      open={sourceId !== null}
      onClose={onClose}
      onBack={onBack}
      eyebrow={<Eyebrow>Source provenance</Eyebrow>}
      title={title}
    >
      {res.error && <ErrorNotice error={res.error} context="Could not load the source" />}
      {!s && !res.error && <p className="text-[13px] text-ink-muted">Loading source…</p>}
      {s && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="muted">{humanise(s.origin)}</Badge>
            <Badge tone="muted">{humanise(s.source_type)}</Badge>
            <Badge tone={s.classification.confidentiality === "public" ? "muted" : "warn"}>
              {humanise(s.classification.confidentiality)}
            </Badge>
            {s.classification.personal_data !== "none" && (
              <Badge tone="warn">
                Personal data: {humanise(s.classification.personal_data)}
                {s.classification.pseudonymised ? " (pseudonymised)" : ""}
              </Badge>
            )}
            {s.synthetic && <SyntheticBadge />}
            {s.injection_flags.length > 0 && <FlagBadges flags={["injection_suspected"]} />}
          </div>
          <KeyValues
            rows={[
              ["Publisher", s.publisher ?? "—"],
              [
                "URL",
                s.canonical_url ? (
                  <a href={s.canonical_url} target="_blank" rel="noopener noreferrer nofollow" className="break-all text-accent hover:underline">
                    {s.canonical_url}
                  </a>
                ) : (
                  "— (not a web source)"
                ),
              ],
              ["Domain", s.domain ?? "—"],
              ["Published", formatDate(s.published_on)],
              ["Updated", formatDate(s.updated_on)],
              ["Retrieved", formatDateTime(s.retrieved_at)],
              ["Retrieval", `${humanise(s.retrieval_method)}${s.retrieval_provider ? ` via ${s.retrieval_provider}` : ""}`],
              ["Discovered by task", s.discovered_by_task_id ? <Mono>{s.discovered_by_task_id}</Mono> : "—"],
              ["Privacy document", s.privacy_document_id ? <Mono>{s.privacy_document_id}</Mono> : "—"],
              ["Content hash", s.content_hash ? <Mono>{s.content_hash.slice(0, 16)}…</Mono> : "—"],
              ["Injection flags", s.injection_flags.length ? s.injection_flags.join(", ") : "None"],
            ]}
          />
          <section>
            <Eyebrow className="mb-1">Sanitised content</Eyebrow>
            <p className="mb-2 text-xs text-ink-muted">
              Content as stored after the privacy gateway. Raw confidential text never reaches the browser.
            </p>
            {s.content ? (
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded border border-line bg-surface-muted p-3 font-mono text-[12px] text-ink">
                {s.content}
              </pre>
            ) : (
              <EmptyState>No stored content for this source.</EmptyState>
            )}
          </section>
          <section>
            <Eyebrow className="mb-2">Evidence extracted from this source ({derived.length})</Eyebrow>
            <div className="space-y-2">
              {derived.map((e) => (
                <EvidenceCard key={e.id} evidence={e} source={lookups.sources.get(e.source_id)} onOpenSource={openSource} />
              ))}
            </div>
          </section>
        </div>
      )}
    </Drawer>
  );
}
