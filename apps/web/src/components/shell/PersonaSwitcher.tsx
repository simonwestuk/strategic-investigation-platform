"use client";

import { usePersona } from "@/lib/hooks";
import { PERSONA_KEYS, PERSONAS, type PersonaKey, describeRoles, personaStore } from "@/lib/roles";

/**
 * Dev-auth persona switcher. The selected persona's identity and roles are sent as X-User-* headers;
 * the server enforces RBAC. Persisted in localStorage.
 */
export function PersonaSwitcher() {
  const persona = usePersona();
  return (
    <div className="flex items-center gap-2 text-[13px]">
      <label htmlFor="persona" className="text-ink-muted">
        Acting as
      </label>
      <select
        id="persona"
        value={persona.key}
        onChange={(e) => personaStore.set(e.target.value as PersonaKey)}
        className="rounded border border-line-strong bg-surface px-2 py-1 text-[13px] text-ink"
        aria-describedby="persona-roles"
      >
        {PERSONA_KEYS.map((k) => (
          <option key={k} value={k}>
            {PERSONAS[k].label} — {PERSONAS[k].displayName}
          </option>
        ))}
      </select>
      <span id="persona-roles" className="hidden text-xs text-ink-subtle xl:inline">
        Roles: {describeRoles(persona.roles)}
      </span>
    </div>
  );
}
