"use client";

import { createContext, useContext } from "react";
import type { Lookups } from "@/lib/decision-room";
import type { Persona } from "@/lib/roles";
import type { InvestigationDetail } from "@/lib/types";
import type { SectionId } from "./sections";

export interface WorkspaceApi {
  detail: InvestigationDetail;
  lookups: Lookups;
  persona: Persona;
  openClaim: (claimId: string) => void;
  openSource: (sourceId: string) => void;
  openDocument: (documentId: string) => void;
  goTo: (section: SectionId) => void;
  reload: () => void;
}

const Ctx = createContext<WorkspaceApi | null>(null);

export const WorkspaceProvider = Ctx.Provider;

export function useWorkspace(): WorkspaceApi {
  const v = useContext(Ctx);
  if (!v) throw new Error("useWorkspace must be used inside <WorkspaceProvider>");
  return v;
}
