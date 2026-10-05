/**
 * Minimal localStorage-backed store usable with React's `useSyncExternalStore`.
 * Every storage access is wrapped: storage can be unavailable (private mode, blocked site data,
 * server rendering) and the UI must still work with the default value.
 */
export interface PersistentStore<T extends string> {
  get(): T;
  set(value: T): void;
  subscribe(listener: () => void): () => void;
  serverSnapshot(): T;
}

export function readStorage(key: string): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable; the in-memory value still applies for this page view.
  }
}

export function createPersistentStore<T extends string>(
  key: string,
  fallback: T,
  isValid: (value: string) => value is T,
): PersistentStore<T> {
  const listeners = new Set<() => void>();
  let memory: T | null = null;

  const get = (): T => {
    if (memory !== null) return memory;
    const stored = readStorage(key);
    memory = stored !== null && isValid(stored) ? stored : fallback;
    return memory;
  };

  return {
    get,
    set(value) {
      memory = value;
      writeStorage(key, value);
      listeners.forEach((l) => l());
    },
    subscribe(listener) {
      listeners.add(listener);
      const onStorage = (e: StorageEvent) => {
        if (e.key === key) {
          memory = null;
          listener();
        }
      };
      if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
      return () => {
        listeners.delete(listener);
        if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
      };
    },
    serverSnapshot: () => fallback,
  };
}
