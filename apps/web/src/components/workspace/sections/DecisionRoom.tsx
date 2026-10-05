"use client";

import { bucketKnowledge, furtherInvestigation } from "@/lib/decision-room";
import { CausalPicturePanel } from "../decision/CausalPicturePanel";
import { FurtherInvestigationPanel } from "../decision/FurtherInvestigationPanel";
import { HumanDecisionPanel } from "../decision/HumanDecisionPanel";
import { KnowledgeColumns } from "../decision/KnowledgeColumns";
import { OptionsPanel } from "../decision/OptionsPanel";
import { useWorkspace } from "../WorkspaceContext";
import { SectionHeading } from "../../ui/Panel";

export function DecisionRoom() {
  const { detail } = useWorkspace();
  const buckets = bucketKnowledge(detail);
  const further = furtherInvestigation(detail);
  const hasAnalysis = detail.claims.length > 0 || detail.hypotheses.length > 0;

  return (
    <div className="space-y-6">
      <SectionHeading
        title="Decision Room"
        description="What the evidence supports, what it does not, what remains unknown, and the options for leadership. Options are AI recommendations; only an accountable person records a decision."
      />
      {!hasAnalysis ? (
        <p className="rounded border border-dashed border-line px-4 py-6 text-center text-[13px] text-ink-muted">
          No analysis yet. The causal picture, classified claims and options appear here once research has run
          {detail.pending_review_id ? " — the investigation is currently waiting for a human review (see Governance & reviews)." : "."}
        </p>
      ) : (
        <>
          <CausalPicturePanel />
          <KnowledgeColumns buckets={buckets} />
          <OptionsPanel />
          <FurtherInvestigationPanel items={further} />
        </>
      )}
      <HumanDecisionPanel />
    </div>
  );
}
