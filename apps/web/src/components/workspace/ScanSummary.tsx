import { humanise } from "@/lib/format";
import type { DataClassification, EntityCount, PrivacyScanSummary } from "@/lib/types";
import { Badge } from "../ui/Badge";

export function ClassificationTags({ c }: { c: DataClassification }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      <Badge tone={c.confidentiality === "public" ? "muted" : c.confidentiality === "restricted" ? "danger" : "warn"}>
        {humanise(c.confidentiality)}
      </Badge>
      <Badge tone={c.personal_data === "special_category" ? "danger" : c.personal_data === "personal" ? "warn" : "muted"}>
        {c.personal_data === "none" ? "No personal data" : `${humanise(c.personal_data)} data`}
      </Badge>
      {c.pseudonymised && <Badge tone="info">Pseudonymised</Badge>}
    </span>
  );
}

export function EntityTable({ counts }: { counts: readonly EntityCount[] }) {
  if (counts.length === 0) return <p className="text-xs text-ink-subtle">No entities detected.</p>;
  return (
    <table className="w-full text-left text-xs">
      <thead className="text-ink-muted">
        <tr>
          <th className="py-1 pr-2 font-medium">Entity</th>
          <th className="py-1 pr-2 font-medium">Detected</th>
          <th className="py-1 font-medium">Low confidence</th>
        </tr>
      </thead>
      <tbody>
        {counts.map((e) => (
          <tr key={e.entity_type} className="border-t border-line">
            <td className="py-1 pr-2 font-mono">{e.entity_type}</td>
            <td className="py-1 pr-2 tabular-nums">{e.count}</td>
            <td className="py-1 tabular-nums">
              {e.low_confidence > 0 ? <span className="font-semibold text-warn-fg">{e.low_confidence} ⚠</span> : 0}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Privacy gateway scan: what was detected and how it was classified. Never shows raw content. */
export function ScanSummary({ scan }: { scan: PrivacyScanSummary }) {
  const declaredDiffers =
    scan.declared_classification.confidentiality !== scan.classification.confidentiality ||
    scan.declared_classification.personal_data !== scan.classification.personal_data;
  return (
    <div className="space-y-2 text-[13px]">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs text-ink-muted">Detected classification</span>
        <ClassificationTags c={scan.classification} />
      </div>
      {declaredDiffers && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-ink-muted">Declared on upload</span>
          <ClassificationTags c={scan.declared_classification} />
        </div>
      )}
      <EntityTable counts={scan.entity_counts} />
      <p className="text-xs text-ink-muted">
        Detector <span className="font-mono">{scan.detector}</span> · {scan.pseudonym_tokens} pseudonym tokens ·{" "}
        {scan.low_confidence_detections} low-confidence detections · {scan.special_category_spans} special-category spans
        {scan.special_category_types.length > 0 && ` (${scan.special_category_types.join(", ")})`}
        {scan.confidentiality_markers.length > 0 && ` · markers: ${scan.confidentiality_markers.join(", ")}`}
      </p>
    </div>
  );
}
