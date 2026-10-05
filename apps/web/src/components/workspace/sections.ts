export const SECTIONS = [
  { id: "decision-room", label: "Summary" },
  { id: "hypotheses", label: "Hypothesis map" },
  { id: "research", label: "Research activity" },
  { id: "evidence", label: "Evidence ledger" },
  { id: "claims", label: "Claims" },
  { id: "challenges", label: "Contradictions & challenges" },
  { id: "governance", label: "Governance & reviews" },
  { id: "privacy", label: "Privacy intake" },
  { id: "audit", label: "Audit trail" },
] as const;

export type SectionId = (typeof SECTIONS)[number]["id"];

export const DEFAULT_SECTION: SectionId = "decision-room";

export function toSectionId(hash: string): SectionId {
  const h = hash.replace(/^#/, "");
  return SECTIONS.some((s) => s.id === h) ? (h as SectionId) : DEFAULT_SECTION;
}
