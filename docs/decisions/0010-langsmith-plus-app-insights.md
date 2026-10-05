# 0010 — LangSmith for agent behaviour, Application Insights for the platform

**Context.** Agent debugging needs run trees, prompts, token usage and experiment comparison;
operations needs request metrics, errors and infrastructure telemetry in Azure.

**Decision.** LangSmith via LangGraph's native tracing plus `wrap_openai`, with investigation/task/agent
metadata and a content policy (`SIP_TRACE_CONTENT`). structlog JSON logs (no content) exported to
Application Insights via `azure-monitor-opentelemetry` when configured.

**Consequences.** Each tool is used for what it is good at. Cost: two systems; traces of sanitised
content still leave the tenant when LangSmith is SaaS (use `metadata_only` or self-hosted LangSmith if
that is unacceptable).
