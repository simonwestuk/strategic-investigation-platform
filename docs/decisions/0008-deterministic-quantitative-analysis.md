# 0008 — Quantitative analysis in code over role-based datasets

**Context.** "Is the decline market-wide or ours?" is arithmetic. LLMs do it unreliably, and embedding a
CSV for RAG answers it worse.

**Decision.** Datasets are registered with a role manifest (own volume, market volume, funnel, customer
destination…). A catalogue of typed operations (`own_vs_market`, `decompose_change`, `funnel_conversion`,
`compare_groups`, `trend`) computes results and emits coded *patterns*; the driver taxonomy maps patterns to
hypothesis stances. Models choose operations; they never compute. Missing roles are recorded as
unavailable evidence.

**Consequences.** Correct, reproducible numbers with provenance (the query is the locator); the
challenger can commission disconfirming tests (difference-in-change). Cost: new analytical questions
need new operations.
