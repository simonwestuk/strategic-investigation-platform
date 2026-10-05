# Architectural decision records

| # | Decision | Status |
|---|---|---|
| [0001](0001-langgraph-orchestration.md) | LangGraph for orchestration, not a single autonomous agent | Accepted |
| [0002](0002-model-proposes-rules-dispose.md) | The model proposes; deterministic rules dispose (two reasoner implementations) | Accepted |
| [0003](0003-separate-evidence-claim-finding.md) | Separate Source, Evidence, Claim, Finding, Recommendation, Decision | Accepted |
| [0004](0004-postgresql-entity-tables-json-payloads.md) | PostgreSQL with per-entity tables and JSON payloads | Accepted |
| [0005](0005-privacy-gateway-before-agent-boundary.md) | Privacy gateway before the agent boundary; never send raw data to the LLM | Accepted |
| [0006](0006-human-only-decision.md) | Decision is a human-only type created only from an interrupt | Accepted |
| [0007](0007-governance-as-policy-pack.md) | Governance as a machine-readable policy pack, fail closed | Accepted |
| [0008](0008-deterministic-quantitative-analysis.md) | Quantitative analysis in code over role-based datasets | Accepted |
| [0009](0009-search-provider-abstraction.md) | Search behind an interface; Tavily/Brave live, offline corpus for evaluation | Accepted |
| [0010](0010-langsmith-plus-app-insights.md) | LangSmith for agent behaviour, Application Insights for the platform | Accepted |
| [0011](0011-azure-ai-search-optional.md) | Azure AI Search is optional at V1 scale | Accepted |
| [0012](0012-generic-driver-taxonomy.md) | A generic driver taxonomy instead of domain-specific hypotheses | Accepted |
