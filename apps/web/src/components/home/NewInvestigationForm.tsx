"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { USE_FIXTURES } from "@/lib/env";
import { type Persona, hasRole } from "@/lib/roles";
import type { Scenario } from "@/lib/types";
import { ErrorNotice } from "../ErrorNotice";
import { Button, inputClass, labelClass } from "../ui/Button";

type Mode = "scenario" | "adhoc";

export function NewInvestigationForm({ scenarios, persona }: { scenarios: Scenario[]; persona: Persona }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("scenario");
  const [scenarioId, setScenarioId] = useState("");
  const [question, setQuestion] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [context, setContext] = useState("");
  const [maxIterations, setMaxIterations] = useState(4);
  const [startNow, setStartNow] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const allowed = hasRole(persona.roles, "investigator");
  const chosen = scenarioId || scenarios[0]?.id || "";
  const scenario = scenarios.find((s) => s.id === chosen);
  const valid = mode === "scenario" ? Boolean(chosen) : question.trim().length >= 10;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createInvestigation(
        mode === "scenario"
          ? { scenario_id: chosen, context, budget: { max_iterations: maxIterations } }
          : { question: question.trim(), organisation: organisation.trim() || null, context, budget: { max_iterations: maxIterations } },
      );
      if (startNow) await api.startInvestigation(created.id);
      router.push(`/investigations/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      {!allowed && (
        <p className="rounded bg-warn-bg px-2.5 py-1.5 text-xs text-warn-fg">
          You are acting as <strong>{persona.label}</strong>. Creating investigations requires the Investigator role —
          switch persona in the header.
        </p>
      )}
      {USE_FIXTURES && (
        <p className="rounded bg-surface-muted px-2.5 py-1.5 text-xs text-ink-muted">
          Fixture mode is read-only: creating an investigation needs the live API.
        </p>
      )}
      <fieldset disabled={!allowed || busy} className="space-y-3">
        <div role="radiogroup" aria-label="Question source" className="flex gap-4 text-[13px]">
          <label className="flex items-center gap-1.5">
            <input type="radio" name="mode" checked={mode === "scenario"} onChange={() => setMode("scenario")} />
            From a scenario
          </label>
          <label className="flex items-center gap-1.5">
            <input type="radio" name="mode" checked={mode === "adhoc"} onChange={() => setMode("adhoc")} />
            Ad-hoc question
          </label>
        </div>

        {mode === "scenario" ? (
          <div>
            <label htmlFor="scenario" className={labelClass}>
              Scenario
            </label>
            <select id="scenario" className={inputClass} value={chosen} onChange={(e) => setScenarioId(e.target.value)}>
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
            {scenario && (
              <div className="mt-2 rounded border border-line bg-surface-muted px-2.5 py-2 text-xs text-ink-muted">
                <p className="text-ink">{scenario.question}</p>
                <p className="mt-1">
                  {scenario.organisation} · {scenario.datasets} datasets · {scenario.documents} documents (synthetic)
                </p>
              </div>
            )}
          </div>
        ) : (
          <>
            <div>
              <label htmlFor="question" className={labelClass}>
                Strategic question
              </label>
              <textarea
                id="question"
                rows={3}
                className={inputClass}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Why has … declined, and what should leadership do?"
              />
            </div>
            <div>
              <label htmlFor="org" className={labelClass}>
                Organisation (optional)
              </label>
              <input id="org" className={inputClass} value={organisation} onChange={(e) => setOrganisation(e.target.value)} />
            </div>
          </>
        )}

        <div>
          <label htmlFor="context" className={labelClass}>
            Decision context (optional)
          </label>
          <textarea id="context" rows={2} className={inputClass} value={context} onChange={(e) => setContext(e.target.value)} />
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div>
            <label htmlFor="iters" className={labelClass}>
              Max research iterations
            </label>
            <input
              id="iters"
              type="number"
              min={1}
              max={8}
              className={`${inputClass} w-24`}
              value={maxIterations}
              onChange={(e) => setMaxIterations(Math.max(1, Math.min(8, Number(e.target.value) || 1)))}
            />
          </div>
          <label className="flex items-center gap-1.5 pb-1.5 text-[13px]">
            <input type="checkbox" checked={startNow} onChange={(e) => setStartNow(e.target.checked)} />
            Start research immediately
          </label>
        </div>
        {error && <ErrorNotice error={error} />}
        <Button type="submit" variant="primary" disabled={!valid || busy}>
          {busy ? "Creating…" : "Create investigation"}
        </Button>
      </fieldset>
    </form>
  );
}
