"use client";

import { type FormEvent, useRef, useState } from "react";
import { api } from "@/lib/api";
import { USE_FIXTURES } from "@/lib/env";
import { formatDateTime, humanise } from "@/lib/format";
import { hasRole } from "@/lib/roles";
import type { Confidentiality, SourceType } from "@/lib/types";
import { ErrorNotice } from "../../ErrorNotice";
import { Badge, type Tone } from "../../ui/Badge";
import { Button, inputClass, labelClass } from "../../ui/Button";
import { EmptyState, Mono, Panel, SectionHeading } from "../../ui/Panel";
import { ScanSummary } from "../ScanSummary";
import { useWorkspace } from "../WorkspaceContext";

const STATUS_TONE: Record<string, Tone> = { released: "ok", pending_release: "warn", rejected: "danger", withheld: "danger" };

const SOURCE_TYPES: SourceType[] = ["internal_document", "internal_dataset", "crm_record", "human_supplied"];
const CONFIDENTIALITY: Confidentiality[] = ["public", "internal", "commercially_confidential", "restricted"];

function UploadForm() {
  const { detail, persona, reload } = useWorkspace();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState<SourceType>("internal_document");
  const [confidentiality, setConfidentiality] = useState<Confidentiality>("internal");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const allowed = hasRole(persona.roles, "investigator");

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const doc = await api.uploadDocument(detail.summary.id, { file, title: title.trim() || undefined, sourceType, confidentiality });
      setDone(`“${doc.title}” scanned: ${humanise(doc.status)}.`);
      setFile(null);
      setTitle("");
      if (fileRef.current) fileRef.current.value = "";
      reload();
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Panel title="Upload a document" subtitle="Goes through the privacy gateway: detection, pseudonymisation and release policy. Requires the Investigator role.">
      <form onSubmit={submit} className="space-y-3">
        {!allowed && (
          <p className="rounded bg-warn-bg px-2.5 py-1.5 text-xs text-warn-fg">
            Acting as {persona.label}: uploading requires the Investigator role.
          </p>
        )}
        {USE_FIXTURES && <p className="rounded bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted">Uploads need the live API.</p>}
        <fieldset disabled={!allowed || busy} className="grid gap-3 md:grid-cols-2">
          <div>
            <label htmlFor="up-file" className={labelClass}>
              File (.txt, .md, .csv, .pdf, .docx — per backend limits)
            </label>
            <input
              id="up-file"
              ref={fileRef}
              type="file"
              className="block w-full text-[13px] file:mr-2 file:rounded file:border file:border-line-strong file:bg-surface file:px-2 file:py-1"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
          </div>
          <div>
            <label htmlFor="up-title" className={labelClass}>
              Title (optional)
            </label>
            <input id="up-title" className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <label htmlFor="up-type" className={labelClass}>
              Source type
            </label>
            <select id="up-type" className={inputClass} value={sourceType} onChange={(e) => setSourceType(e.target.value as SourceType)}>
              {SOURCE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {humanise(t)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="up-conf" className={labelClass}>
              Declared confidentiality
            </label>
            <select
              id="up-conf"
              className={inputClass}
              value={confidentiality}
              onChange={(e) => setConfidentiality(e.target.value as Confidentiality)}
            >
              {CONFIDENTIALITY.map((t) => (
                <option key={t} value={t}>
                  {humanise(t)}
                </option>
              ))}
            </select>
          </div>
        </fieldset>
        {error && <ErrorNotice error={error} context="Upload failed" />}
        {done && <p className="text-[13px] text-ok-fg" role="status">{done}</p>}
        <Button type="submit" variant="primary" disabled={!allowed || busy || !file}>
          {busy ? "Scanning…" : "Upload through privacy gateway"}
        </Button>
      </form>
    </Panel>
  );
}

export function PrivacyIntake() {
  const { detail, openDocument } = useWorkspace();
  return (
    <div className="space-y-6">
      <SectionHeading
        title="Privacy intake"
        description="Internal material enters agent context only through the privacy gateway. Only sanitised text is ever stored for agents or served to this UI; documents that need a human decision wait for a privacy reviewer."
      />
      {detail.intake.length === 0 ? (
        <EmptyState>No documents have been ingested.</EmptyState>
      ) : (
        <ul className="grid gap-3 xl:grid-cols-2">
          {detail.intake.map((d) => (
            <li key={d.id} className="rounded-md border border-line bg-surface px-4 py-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h3 className="text-[13px] font-semibold">{d.title}</h3>
                  <p className="text-xs text-ink-subtle">
                    <Mono>{d.filename}</Mono> · {humanise(d.kind)} · {humanise(d.source_type)} · uploaded by {d.uploaded_by}{" "}
                    {formatDateTime(d.uploaded_at)}
                  </p>
                </div>
                <Badge tone={STATUS_TONE[d.status] ?? "neutral"}>{humanise(d.status)}</Badge>
              </div>
              <div className="mt-2">
                <ScanSummary scan={d.scan} />
              </div>
              <Button variant="ghost" className="mt-2 -ml-3" onClick={() => openDocument(d.id)}>
                View sanitised text →
              </Button>
            </li>
          ))}
        </ul>
      )}
      <UploadForm />
    </div>
  );
}
