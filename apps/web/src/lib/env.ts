/** Build-time configuration. `NEXT_PUBLIC_*` values are inlined by Next.js at build time. */
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(/\/+$/, "");

export const USE_FIXTURES = process.env.NEXT_PUBLIC_USE_FIXTURES === "true";
