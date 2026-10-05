# Investigation Workspace (web)

Next.js (App Router) + React 19 + TypeScript (strict) + Tailwind CSS v4 frontend for the Strategic Investigation Platform.

> Autonomous research. Governed reasoning. Human decisions.

The UI presents an investigation the way a decision-maker needs it: what is **known**, **inferred**, **hypothesised** and **unknown**; what contradicts the current explanation; which strategic options the agents **recommend** (always labelled as AI recommendations); and a human-only decision form that cannot be submitted until every unresolved unknown has been explicitly acknowledged.

## Running

```bash
npm ci

# Live API (backend on http://localhost:8000, dev auth mode)
npm run dev                                   # http://localhost:3000

# Fixture mode: no backend, serves real captured responses from ./fixtures
NEXT_PUBLIC_USE_FIXTURES=true npm run dev
```

Fixture mode shows a banner with a **Snapshot** selector (privacy review → options review → awaiting decision → decided). Responding to a review moves on to the next snapshot, and a submitted decision is merged into the final snapshot under the active persona. Creating, starting and uploading need the live API.

The backend's CORS default (`SIP_CORS_ORIGINS=http://localhost:3000`) matches `npm run dev`.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | FastAPI base URL |
| `NEXT_PUBLIC_USE_FIXTURES` | `false` | `true` serves `fixtures/*.json` instead of calling the API |

Both are `NEXT_PUBLIC_*`, so they are **inlined at build time**. Set them before `npm run build` (or as Docker build args), not only at runtime. `next.config.ts` sets `output: "standalone"` for the container image.

### Personas and RBAC

Dev auth sends `X-User-Id`, `X-User-Name` and `X-User-Roles` headers. The header's **Acting as** switcher (saved in `localStorage`) offers Investigator, Privacy reviewer, Governance reviewer, Decision-maker, Viewer (read-only) and All roles (demo). Every pending review shows the role it needs. When the current persona lacks that role, the form is disabled and the reason is given. The server still enforces RBAC on its own and returns 403.

## Scripts

| Script | What it does |
| --- | --- |
| `dev` / `build` / `start` | Next.js |
| `lint` | ESLint (`eslint-config-next` core-web-vitals + TypeScript) |
| `typecheck` | `next typegen && tsc --noEmit` (typegen produces `PageProps`/`LayoutProps`) |
| `test` | Vitest + Testing Library (jsdom) |
| `gen:api` | Regenerates `src/lib/api-types.ts` from `fixtures/openapi.json` with `openapi-typescript` |
| `screenshots` | Captures `docs/images/*.png` from a running fixture-mode server (uses local Chrome) |

To regenerate the screenshots:

```bash
NEXT_PUBLIC_USE_FIXTURES=true npm run build && npx next start -p 3100 &
BASE_URL=http://localhost:3100 npm run screenshots
```

## Structure

```
fixtures/                 Real API responses (+ openapi.json) used by fixture mode and tests
src/app/                  Routes: / (investigations) and /investigations/[id] (workspace)
src/lib/
  api-types.ts            GENERATED from OpenAPI — do not edit
  types.ts                Domain aliases; Resp<T> makes response defaults non-optional
  api.ts                  Typed client (persona headers, ApiError); fixture-api.ts is code-split
  causal.ts               Hypothesis tree → causal picture (drivers by segment)
  decision-room.ts        Knowledge buckets, further investigation, option evidence chain
  claim-chain.ts          Client-side /claims/{id} equivalent (fixture mode)
  reviews.ts              Review form state → ReviewResponseIn payloads + validation
  review-context.ts       Narrowing parsers for the untyped HumanReview.context
  evidence.ts, research.ts, format.ts, labels.ts, roles.ts, hooks.ts, storage.ts
src/components/
  ui/                     Badges (classification, confidence, statuses), Panel, Drawer, Button
  shell/                  App header, persona switcher, fixture banner
  home/                   Investigation list and new-investigation form
  workspace/              Header, section nav, drawers (claim chain, source, document)
    sections/             Decision Room, Hypothesis map, Research, Evidence ledger, Claims,
                          Contradictions & challenges, Governance, Privacy intake, Audit trail
    decision/             Causal picture, knowledge columns, options, further investigation, decision
    reviews/              One form per review kind + shared optional fields and history
```

Workspace sections are addressed by URL hash (e.g. `/investigations/inv_…#claims`). While `summary.status === "running"`, the workspace polls every 2 s.

### Visual language

The four classifications are told apart by more than colour: each has a text label, a glyph and its own border style. KNOWN ■ is solid green, INFERRED ◩ is solid blue, HYPOTHESIS ◇ has a dotted amber border, and UNKNOWN ? has a dashed grey border. Strategic options sit in dashed violet "AI recommendation · not a decision" cards. A recorded decision sits in a solid dark-bordered "Human decision" panel that shows who decided and when. Synthetic sources carry a `synthetic` badge. Dark mode follows `prefers-color-scheme`.

## Dependencies

Runtime: `next`, `react`, `react-dom`, and `clsx` (class composition). There is no UI kit. Native `<dialog>` and `<details>` provide focus handling and disclosure.
Dev: `typescript`, `eslint` + `eslint-config-next`, `tailwindcss` + `@tailwindcss/postcss`, `openapi-typescript`, `vitest` + `@vitejs/plugin-react` + `jsdom` + Testing Library, and `@playwright/test` (screenshot script only).

## Known API gaps

- The `GET /audit` and `GET /documents/{id}` responses are untyped in OpenAPI (`list[Any]` / `dict`), so `AuditEvent` and `DocumentDetail` are written by hand in `types.ts`.
- `HumanReview.context` is an untyped dict. `review-context.ts` parses it defensively for each review kind.
- FastAPI emits fields that have defaults as optional. The client relies on responses always including them (`Resp<T>`).
