import { ROLE_LABELS, TEAM_MODE, describeRoles, hasRole, type Persona } from "@/lib/roles";
import type { Role } from "@/lib/types";

/** Explains, before the user tries, whether the current persona may respond to this review. */
export function RoleGate({ required, persona }: { required: Role; persona: Persona }) {
  const ok = hasRole(persona.roles, required);
  if (!TEAM_MODE) return null; // single operator: every approval is yours
  return (
    <p
      className={
        ok
          ? "rounded bg-ok-bg px-3 py-1.5 text-xs text-ok-fg"
          : "rounded border border-warn-fg/30 bg-warn-bg px-3 py-1.5 text-xs text-warn-fg"
      }
    >
      Requires the <strong>{ROLE_LABELS[required]}</strong> role.{" "}
      {ok
        ? `You are acting as ${persona.displayName} (${describeRoles(persona.roles)}) and can respond.`
        : `You are acting as ${persona.displayName} (${describeRoles(persona.roles)}), so the actions below are disabled. Switch persona in the header to respond. The server enforces this independently.`}
    </p>
  );
}
