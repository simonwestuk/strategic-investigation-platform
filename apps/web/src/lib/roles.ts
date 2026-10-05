import type { Role } from "./types";
import { createPersistentStore } from "./storage";

export const ROLE_LABELS: Record<Role, string> = {
  viewer: "Viewer",
  investigator: "Investigator",
  privacy_reviewer: "Privacy reviewer",
  governance_reviewer: "Governance reviewer",
  decision_maker: "Decision-maker",
  admin: "Administrator",
};

export interface Persona {
  key: PersonaKey;
  label: string;
  userId: string;
  displayName: string;
  roles: Role[];
}

export const PERSONA_KEYS = ["investigator", "privacy", "governance", "decision", "viewer", "demo"] as const;
export type PersonaKey = (typeof PERSONA_KEYS)[number];

export const PERSONAS: Record<PersonaKey, Persona> = {
  investigator: {
    key: "investigator",
    label: "Investigator",
    userId: "alex.morgan",
    displayName: "Alex Morgan",
    roles: ["investigator"],
  },
  privacy: {
    key: "privacy",
    label: "Privacy reviewer",
    userId: "priya.shah",
    displayName: "Priya Shah",
    roles: ["privacy_reviewer"],
  },
  governance: {
    key: "governance",
    label: "Governance reviewer",
    userId: "gareth.lewis",
    displayName: "Gareth Lewis",
    roles: ["governance_reviewer"],
  },
  decision: {
    key: "decision",
    label: "Decision-maker",
    userId: "dana.okafor",
    displayName: "Dana Okafor",
    roles: ["decision_maker"],
  },
  viewer: {
    key: "viewer",
    label: "Viewer (read-only)",
    userId: "sam.reader",
    displayName: "Sam Reader",
    roles: ["viewer"],
  },
  demo: {
    key: "demo",
    label: "All roles (demo)",
    userId: "demo",
    displayName: "Demo User",
    roles: ["investigator", "privacy_reviewer", "governance_reviewer", "decision_maker"],
  },
};

export const DEFAULT_PERSONA: PersonaKey = "demo";

function isPersonaKey(value: string): value is PersonaKey {
  return (PERSONA_KEYS as readonly string[]).includes(value);
}

export const personaStore = createPersistentStore<PersonaKey>("sip.persona", DEFAULT_PERSONA, isPersonaKey);

export function getPersona(): Persona {
  return PERSONAS[personaStore.get()];
}

/** Mirrors the server's `Actor.has_role`: admin implies every role. */
export function hasRole(roles: readonly Role[], required: Role): boolean {
  return roles.includes(required) || roles.includes("admin");
}

/** Dev-auth headers understood by the FastAPI backend (`SIP_AUTH_MODE=dev`). */
export function personaHeaders(p: Persona): Record<string, string> {
  return {
    "X-User-Id": p.userId,
    "X-User-Name": p.displayName,
    "X-User-Roles": p.roles.join(","),
  };
}

export function describeRoles(roles: readonly Role[]): string {
  return roles.map((r) => ROLE_LABELS[r]).join(", ");
}
