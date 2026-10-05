# Implementation Plan

Status: living document. Written at the start of the V1 build (October 2026) after an inventory of the
initial scaffold; updated as decisions change.

---

## 1. Current-state assessment (scaffold at commit `b96efaa`)

### Inventory

| Area | What exists | Size |
|---|---|---|
| Domain | `sip/domain/models.py` — one module with Investigation, Hypothesis, Source, Evidence, Claim, ResearchTask, DecisionOption, HumanReview | ~150 lines |
| Graph | `sip/graph/build.py`, `state.py` — linear 8-node graph with one conditional loop | ~50 lines |
| Nodes | `sip/nodes/core.py` — deterministic placeholders; hypotheses hard-coded to the apprenticeship scenario | ~100 lines |
| Governance | `sip/governance/policy.py` — three `if` statements returning a risk level | ~25 lines |
| Privacy | `sip/privacy/gateway.py` — regex redaction of emails and UK phone numbers to `[EMAIL]`/`[PHONE]` | ~30 lines |
| Tests | Two smoke tests | ~15 lines |
| Docs | Short README and architecture note | — |
| Tooling | `pyproject.toml` with loose lower bounds; no lockfile, no Ruff rules, no type checking, no CI | — |

Total: ~380 lines of Python. No frontend, persistence, API routes, model provider, research tools,
evaluation, infrastructure or CI.

### Architecture assessment

The scaffold states the right *principles* (separate Source/Evidence/Claim, a privacy boundary, a human
decision gate) but none of them are enforced:

1. **Recommendation/Decision separation is nominal.** There is no `Decision` type at all; `DecisionOption.requires_human_decision` is a boolean nobody reads.
2. **Governance is not machine-readable.** Rules are hard-coded `if` branches over the whole investigation, not over activities. There is no notion of autonomy level, required role or audit requirement.
3. **HITL does not exist.** `governance_gate` sets a flag and the graph ends. No interrupt, no checkpointer, no resume.
4. **Privacy gateway is redaction, not pseudonymisation.** `[EMAIL]` destroys analytical linkage; there is no sensitivity classification, no quarantine of raw content, no review path, and nothing stops raw text reaching an agent.
5. **The graph is a fixed chain.** The loop condition is `not inv.evidence`, i.e. it loops once and stops. Nodes deep-copy the entire investigation on every step, which will not scale and makes parallel research impossible (no reducers).
6. **Scenario logic is in core code.** `generate_hypotheses` hard-codes apprenticeship-specific statements, violating the domain-agnostic requirement.
7. **Confidence is an uncalibrated float** (`confidence: float = 0.5`) with no definition.
8. **Source authority is a single universal score** (`authority_score`) — exactly the simplification the brief rejects.
9. **No persistence, provenance timestamps on evidence, audit trail, budgets, or observability.**
10. **Hygiene:** `__pycache__` files are committed; there is no `.gitignore`.

### Retain

- Package name `sip` and `src/` layout.
- The conceptual vocabulary (KNOWN / INFERRED / HYPOTHESIS / UNKNOWN; Source → Evidence → Claim).
- LangGraph as orchestrator, Pydantic as the domain schema, FastAPI as the API.
- The `.env.example` intent (Azure OpenAI v1 endpoint, LangSmith).

### Replace

- `domain/models.py` → split into focused modules with richer provenance, typed IDs and validators; add `Decision`, `AuditEvent`, `Contradiction`, `Challenge`, `InvestigationFrame`, `ResearchBudget`.
- `nodes/core.py` → agents that depend on a `Reasoner` contract + deterministic tools injected through LangGraph runtime context.
- `governance/policy.py` → YAML policy pack + engine evaluating *activities*.
- `privacy/gateway.py` → staged pipeline (scan → detect → classify → pseudonymise → review → release) with a separate vault.
- `graph/state.py` → typed state with per-collection reducers suitable for parallel fan-out.

### Missing tests

Everything beyond the two smoke tests: routing, governance, privacy boundary, provenance, research providers,
SSRF, prompt injection, persistence, API, evaluation graders.

### Security / privacy concerns found

- No `.gitignore` → risk of committing `.env`.
- No input validation or upload constraints.
- No URL-fetching controls (SSRF) because no fetcher exists yet — must be designed in, not retrofitted.
- Redaction-after-LLM was not present, but neither was any mechanism preventing it.
- Git history contains only scaffold code; no secrets found (`git log -p` reviewed).

---

## 2. Target architecture

```
                      ┌─────────────────────── API boundary (FastAPI, RBAC) ───────────────────────┐
 upload ──► Privacy Gateway (scan → PII detect → sensitivity → pseudonymise → [HITL]) ──► sanitised corpus
                │                                                                        │
                └── raw quarantine + pseudonym vault (separate store; never in agent context)
                                                                                         ▼
 question ──► LangGraph investigation (checkpointed, interruptible)
              frame → privacy_release[HITL] → hypothesise → plan → research ×N (Send fan-out)
              → evidence manager → analyse (rubric) → challenge → route
                    ├─ insufficient & budget left → plan (loop)
                    └─ sufficient / budget spent → findings gate → synthesise → options gate[HITL]
                                                   → decision room [HITL: human-only Decision] → END
              Agents call: Reasoner (LLM or offline) · Tools (search, fetch, datasets, documents)
              · Governance engine · Source-quality + confidence rubric  — all via runtime context
                                                                                         ▼
 projection ──► PostgreSQL (investigations, hypotheses, tasks, sources, evidence, claims, contradictions,
                reviews, options, decisions, audit events) + LangGraph checkpoints
 observability ─► LangSmith (graph/LLM/tool traces, privacy-filtered) · structlog JSON → App Insights
 evaluation ───► scenario ground truth → deterministic graders (+ optional LLM judge) → reports / LangSmith
```

Key design commitments:

1. **The model proposes; deterministic rules dispose.** LLMs frame, hypothesise, plan, extract and argue.
   Classification (KNOWN/INFERRED/...), confidence bands, source quality, budget, governance and privacy
   are computed by inspectable code.
2. **Two reasoner implementations behind one contract.** `LLMReasoner` (Azure OpenAI structured outputs,
   versioned prompt files) and `OfflineReasoner` (deterministic heuristics). The offline reasoner exists for
   CI, credential-free demos and as an evaluation floor — it is not presented as intelligent.
3. **Quantitative analysis is code.** A catalogue of typed analytical operations over datasets described by
   a role manifest (period / segment / measure). Models choose operations; pandas-free plain Python computes.
4. **Web research is real, behind a `SearchProvider` interface** (Tavily, Brave). An `OfflineCorpus`
   provider runs BM25 over a synthetic corpus for CI and reproducible evaluation; it is labelled as such.
5. **Privacy boundary is structural.** Graph runtime context has no reference to raw storage or the vault;
   an architecture test fails if agent/graph modules import them.
6. **Decision is a human-only type** that can only be created from an authenticated human action with the
   `decision_maker` role, via a graph interrupt.

## 3. Workstreams

| # | Workstream | Output |
|---|---|---|
| W1 | Foundations | packaging, settings, logging, `.gitignore`, Ruff/mypy, CI skeleton |
| W2 | Domain | entities, IDs, enums, validators, confidence rubric, source-quality policy |
| W3 | Governance | YAML policy pack, engine, audit events, RBAC roles |
| W4 | Privacy | detectors (local + Azure AI Language), sensitivity classifier, pseudonymiser, vault, quarantine, review |
| W5 | Research tools | search providers, SSRF-safe fetcher, HTML/PDF extraction, injection screening, document index, dataset analytics |
| W6 | Reasoning | model provider abstraction, Azure OpenAI provider, prompts, LLM + offline reasoners, usage/cost |
| W7 | Orchestration | typed state, graph, routing, budgets, interrupts, checkpointing |
| W8 | Persistence & API | SQLAlchemy models, Alembic, projection, service layer, FastAPI routes, auth |
| W9 | Scenarios & evaluation | Northstar synthetic world + ground truth, second scenario, graders, runner, LangSmith upload |
| W10 | Frontend | Next.js Decision Room |
| W11 | Platform | Dockerfiles, Compose, Bicep, GitHub Actions |
| W12 | Documentation | README, architecture, governance, privacy, threat model, RAI, evaluation, deployment, ADRs |

## 4. Ordered phases

1. **Foundations + domain + governance + privacy** (W1–W4) — contracts everything else depends on.
2. **Synthetic world** (W9a) — data designed *before* tools so tools are not tuned to it.
3. **Tools + reasoning** (W5–W6).
4. **Graph** (W7) with routing/HITL tests.
5. **Persistence + API** (W8). API contract frozen here.
6. **Evaluation** (W9b) — run against offline reasoner; establish baseline.
7. **Frontend + platform** (W10–W11) in parallel once the API is frozen.
8. **Documentation pass** (W12) against the implemented system; README last.

## 5. Key risks

| Risk | Mitigation |
|---|---|
| No live Azure/search credentials in the build environment | Providers tested with mocked HTTP; offline mode fully exercised; README is explicit about what was and was not verified live |
| Offline reasoner makes the demo look scripted | Generic, documented heuristics; scenario knowledge lives only in data; evals report offline vs LLM separately |
| Evaluation overfits to the one scenario | Second scenario in a different domain; graders score structure, not prose |
| Unbounded loops / cost | Budget object enforced in routing; hard recursion limit; duplicate-task detection |
| Checkpoint deserialisation of domain types | Explicit msgpack allowlist for `sip.domain` |
| Scope (the brief is very large) | Prioritise the definition of done; record deferred items in the roadmap rather than half-building them |

## 6. Decisions requiring clarification (assumed; flagged for the owner)

1. **Web search provider.** Bing Web Search API was retired in 2025. Assumed: Tavily as default live provider, Brave as alternative, both via env vars. Owner may prefer Azure "Grounding with Bing" via Foundry Agent Service — deferred because it couples research to a proprietary agent runtime.
2. **Synthetic "official" sources.** To avoid fabricating records attributed to real bodies, the offline corpus uses fictional publishers on `.test` domains (e.g. "National Skills Statistics Office (synthetic)"). Live mode retrieves real public sources.
3. **IaC language.** Bicep (Azure-native, no state backend to manage).
4. **Authentication in local dev.** A dev header-based identity provider, disabled when `SIP_ENV=production`.

## 7. Definition of done

As section 49 of the build brief. Progress against it is tracked in the README "Status" section, which
states plainly what has been verified locally, what has been verified only with mocks, and what is roadmap.
