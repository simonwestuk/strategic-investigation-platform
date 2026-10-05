"use client";

import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { ErrorNotice } from "../../ErrorNotice";
import { Drawer } from "../../ui/Drawer";
import { Eyebrow } from "../../ui/Panel";
import { ClaimChainView } from "../ClaimChainView";
import { useWorkspace } from "../WorkspaceContext";

export function ClaimDrawer({ claimId, onClose, onBack }: { claimId: string | null; onClose: () => void; onBack?: () => void }) {
  const { detail, lookups, openSource } = useWorkspace();
  const chain = useAsync(
    () => (claimId ? api.getClaimChain(detail.summary.id, claimId) : Promise.resolve(null)),
    [claimId, detail.summary.id],
  );
  const current = chain.data && chain.data.claim.id === claimId ? chain.data : null;

  return (
    <Drawer open={claimId !== null} onClose={onClose} onBack={onBack} eyebrow={<Eyebrow>Claim chain</Eyebrow>} title="Claim → evidence → source">
      {chain.error && <ErrorNotice error={chain.error} context="Could not load the claim chain" />}
      {!current && !chain.error && <p className="text-[13px] text-ink-muted">Loading claim chain…</p>}
      {current && <ClaimChainView chain={current} onOpenSource={openSource} hypotheses={lookups.hypotheses} />}
    </Drawer>
  );
}
