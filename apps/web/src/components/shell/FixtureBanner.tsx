"use client";

import { USE_FIXTURES } from "@/lib/env";
import { FIXTURE_STAGES, FIXTURE_STAGE_LABELS, type FixtureStage, fixtureStageStore } from "@/lib/fixture-stage";
import { useFixtureStage } from "@/lib/hooks";

/** Only rendered in fixture mode: makes it explicit that data is a captured snapshot, not live. */
export function FixtureBanner() {
  const stage = useFixtureStage();
  if (!USE_FIXTURES) return null;
  return (
    <div data-fixture-banner className="border-b border-line bg-warn-bg text-warn-fg">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-3 gap-y-1 px-4 py-1.5 text-xs md:px-6">
        <strong className="font-semibold">Fixture mode</strong>
        <span>Showing responses captured from the real backend. Nothing is sent to an API.</span>
        <label className="ml-auto flex items-center gap-1.5">
          <span>Snapshot</span>
          <select
            value={stage}
            onChange={(e) => fixtureStageStore.set(e.target.value as FixtureStage)}
            className="rounded border border-line-strong bg-surface px-1.5 py-0.5 text-xs text-ink"
          >
            {FIXTURE_STAGES.map((s) => (
              <option key={s} value={s}>
                {FIXTURE_STAGE_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
