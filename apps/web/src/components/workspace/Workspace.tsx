"use client";

import Link from "next/link";
import { useCallback, useMemo, useState, useSyncExternalStore } from "react";
import { buildLookups } from "@/lib/decision-room";
import { useInvestigation, usePersona } from "@/lib/hooks";
import { Briefing } from "../briefing/Briefing";
import { ErrorNotice } from "../ErrorNotice";
import { ClaimDrawer } from "./drawers/ClaimDrawer";
import { DocumentDrawer } from "./drawers/DocumentDrawer";
import { SourceDrawer } from "./drawers/SourceDrawer";
import { SectionNav } from "./SectionNav";
import { type SectionId, toSectionId } from "./sections";
import { AuditTrail } from "./sections/AuditTrail";
import { ChallengesSection } from "./sections/ChallengesSection";
import { ClaimsSection } from "./sections/ClaimsSection";
import { DecisionRoom } from "./sections/DecisionRoom";
import { EvidenceLedger } from "./sections/EvidenceLedger";
import { GovernanceSection } from "./sections/GovernanceSection";
import { HypothesisMap } from "./sections/HypothesisMap";
import { PrivacyIntake } from "./sections/PrivacyIntake";
import { ResearchActivity } from "./sections/ResearchActivity";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { type WorkspaceApi, WorkspaceProvider } from "./WorkspaceContext";

function subscribeHash(cb: () => void) {
  window.addEventListener("hashchange", cb);
  return () => window.removeEventListener("hashchange", cb);
}

type Open = { kind: "claim" | "source" | "document"; id: string } | null;

export function Workspace({ id }: { id: string }) {
  const { data, error, loading, reload } = useInvestigation(id);
  const persona = usePersona();
  const hash = useSyncExternalStore(subscribeHash, () => window.location.hash, () => "");
  const section = toSectionId(hash);
  // A stack so claim → source → back works naturally.
  const [stack, setStack] = useState<Open[]>([]);
  const open = stack.at(-1) ?? null;

  const push = useCallback((o: NonNullable<Open>) => setStack((s) => [...s, o]), []);
  const goTo = useCallback((s: SectionId) => {
    setStack([]);
    window.location.hash = s;
    window.scrollTo({ top: 0 });
  }, []);

  const lookups = useMemo(() => (data ? buildLookups(data) : null), [data]);

  const ws: WorkspaceApi | null = useMemo(
    () =>
      data && lookups
        ? {
            detail: data,
            lookups,
            persona,
            openClaim: (cid) => push({ kind: "claim", id: cid }),
            openSource: (sid) => push({ kind: "source", id: sid }),
            openDocument: (did) => push({ kind: "document", id: did }),
            goTo,
            reload,
          }
        : null,
    [data, lookups, persona, push, goTo, reload],
  );

  if (!ws) {
    return (
      <div className="mx-auto max-w-[1440px] px-4 py-8 md:px-6">
        {error ? (
          <div className="space-y-3">
            <ErrorNotice error={error} context="Could not load the investigation" />
            <Link href="/" className="text-[13px] text-accent hover:underline">
              ← Back to investigations
            </Link>
          </div>
        ) : (
          <p className="text-[13px] text-ink-muted">{loading ? "Loading investigation workspace…" : "Not found."}</p>
        )}
      </div>
    );
  }

  const close = () => setStack((s) => s.slice(0, -1));
  const closeAll = () => setStack([]);

  const drawers = (
    <>
      <ClaimDrawer claimId={open?.kind === "claim" ? open.id : null} onClose={closeAll} onBack={stack.length > 1 ? close : undefined} />
      <SourceDrawer sourceId={open?.kind === "source" ? open.id : null} onClose={closeAll} onBack={stack.length > 1 ? close : undefined} />
      <DocumentDrawer documentId={open?.kind === "document" ? open.id : null} onClose={closeAll} />
    </>
  );

  // Default: the single-operator briefing. Any section hash opens the full working view.
  if (hash === "" || hash === "#") {
    return (
      <WorkspaceProvider value={ws}>
        <Briefing />
        {drawers}
      </WorkspaceProvider>
    );
  }

  return (
    <WorkspaceProvider value={ws}>
      <div className="border-b border-line bg-surface-muted">
        <div className="mx-auto max-w-[1440px] px-4 py-2 text-sm md:px-6">
          <a href="#" className="text-accent hover:underline">← Back to the briefing</a>
          <span className="ml-2 text-ink-subtle">Full working: every source, claim and decision point.</span>
        </div>
      </div>
      <WorkspaceHeader />
      <div className="mx-auto grid max-w-[1440px] gap-6 px-4 pb-16 pt-4 md:px-6 lg:grid-cols-[200px_minmax(0,1fr)]">
        <SectionNav current={section} />
        <div className="min-w-0">
          {error && (
            <div className="mb-3">
              <ErrorNotice error={error} context="Refresh failed (showing last loaded data)" />
            </div>
          )}
          {section === "decision-room" && <DecisionRoom />}
          {section === "hypotheses" && <HypothesisMap />}
          {section === "research" && <ResearchActivity />}
          {section === "evidence" && <EvidenceLedger />}
          {section === "claims" && <ClaimsSection />}
          {section === "challenges" && <ChallengesSection />}
          {section === "governance" && <GovernanceSection />}
          {section === "privacy" && <PrivacyIntake />}
          {section === "audit" && <AuditTrail />}
        </div>
      </div>
      {drawers}
    </WorkspaceProvider>
  );
}
