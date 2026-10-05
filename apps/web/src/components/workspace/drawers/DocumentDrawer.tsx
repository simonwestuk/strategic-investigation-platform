"use client";

import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { ErrorNotice } from "../../ErrorNotice";
import { Drawer } from "../../ui/Drawer";
import { Eyebrow } from "../../ui/Panel";
import { ScanSummary } from "../ScanSummary";
import { useWorkspace } from "../WorkspaceContext";

export function DocumentDrawer({ documentId, onClose }: { documentId: string | null; onClose: () => void }) {
  const { detail } = useWorkspace();
  const res = useAsync(
    () => (documentId ? api.getDocument(detail.summary.id, documentId) : Promise.resolve(null)),
    [documentId, detail.summary.id],
  );
  const doc = res.data && res.data.id === documentId ? res.data : null;
  return (
    <Drawer open={documentId !== null} onClose={onClose} eyebrow={<Eyebrow>Privacy gateway · sanitised view</Eyebrow>} title={doc?.title ?? "Document"}>
      {res.error && <ErrorNotice error={res.error} context="Could not load the document" />}
      {!doc && !res.error && <p className="text-[13px] text-ink-muted">Loading…</p>}
      {doc && (
        <div className="space-y-4">
          <ScanSummary scan={doc.scan} />
          <section>
            <Eyebrow className="mb-1">Sanitised text</Eyebrow>
            <p className="mb-2 text-xs text-ink-muted">
              Pseudonym tokens (e.g. PERSON_0001) replace detected entities. The original text is never served by the API.
            </p>
            <pre className="max-h-[60vh] overflow-auto whitespace-pre-wrap rounded border border-line bg-surface-muted p-3 font-mono text-[12px]">
              {doc.sanitised_text}
            </pre>
          </section>
        </div>
      )}
    </Drawer>
  );
}
