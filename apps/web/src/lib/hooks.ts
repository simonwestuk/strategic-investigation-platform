"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { api } from "./api";
import { type FixtureStage, fixtureStageStore } from "./fixture-stage";
import { PERSONAS, type Persona, TEAM_MODE, personaStore } from "./roles";
import type { InvestigationDetail } from "./types";

export function usePersona(): Persona {
  const stored = useSyncExternalStore(personaStore.subscribe, personaStore.get, personaStore.serverSnapshot);
  const key = TEAM_MODE ? stored : "operator";
  return PERSONAS[key];
}

export function useFixtureStage(): FixtureStage {
  return useSyncExternalStore(fixtureStageStore.subscribe, fixtureStageStore.get, fixtureStageStore.serverSnapshot);
}

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

/** Loads `fn()` whenever `deps` change. Stale responses are ignored. */
export function useAsync<T>(fn: () => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const [state, setState] = useState<{ data: T | null; error: Error | null; loading: boolean }>({
    data: null,
    error: null,
    loading: true,
  });
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  useEffect(() => {
    let live = true;
    fnRef
      .current()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((error: unknown) =>
        live && setState((s) => ({ data: s.data, error: error instanceof Error ? error : new Error(String(error)), loading: false })),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps are supplied by the caller
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}

export const POLL_INTERVAL_MS = 2000;

/**
 * Loads the investigation workspace and polls every ~2s while the graph is running. The persona
 * and (in fixture mode) the snapshot stage are dependencies, so switching either refreshes.
 */
export function useInvestigation(id: string): AsyncState<InvestigationDetail> {
  const persona = usePersona();
  const stage = useFixtureStage();
  const state = useAsync(() => api.getInvestigation(id), [id, persona.key, stage]);
  const running = state.data?.summary.status === "running";
  const { reload } = state;

  useEffect(() => {
    if (!running) return;
    const t = setInterval(reload, POLL_INTERVAL_MS);
    return () => clearInterval(t);
  }, [running, reload]);

  return state;
}
