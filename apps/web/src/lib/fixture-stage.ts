import { createPersistentStore } from "./storage";

/** Snapshots of the same investigation captured from the real backend at each human gate. */
export const FIXTURE_STAGES = ["privacy-review", "options-review", "awaiting-decision", "decided"] as const;
export type FixtureStage = (typeof FIXTURE_STAGES)[number];

export const FIXTURE_STAGE_LABELS: Record<FixtureStage, string> = {
  "privacy-review": "1 · Privacy release review",
  "options-review": "2 · Options review",
  "awaiting-decision": "3 · Awaiting human decision",
  decided: "4 · Decision recorded",
};

function isStage(value: string): value is FixtureStage {
  return (FIXTURE_STAGES as readonly string[]).includes(value);
}

export const fixtureStageStore = createPersistentStore<FixtureStage>("sip.fixtureStage", "awaiting-decision", isStage);
