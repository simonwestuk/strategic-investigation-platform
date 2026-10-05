# 0009 — Search behind an interface

**Context.** Bing Web Search API was retired in 2025; search providers change; evaluation must be
reproducible and CI must not need keys.

**Decision.** `SearchProvider` and `PageFetcher` protocols. Live: Tavily and Brave (env-configured) with an
SSRF-hardened fetcher. Offline: a per-scenario synthetic corpus with BM25, fictional publishers on
`.test` domains, every source marked `synthetic`. Search snippets are never evidence; pages are fetched
and quoted.

**Consequences.** Swap providers without touching orchestration; deterministic evaluation. Rejected for
V1: Foundry Agent Service "grounding with Bing" (couples research to a proprietary agent runtime).
