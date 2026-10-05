# 0012 — A generic driver taxonomy instead of domain-specific hypotheses

**Context.** The flagship scenario is apprenticeships, but the product must handle churn, sales, market
entry, operations.

**Decision.** A consultant-style issue tree (market contraction, share loss, offer relevance, offer
terms, substitution, demand shift, policy, conversion, pipeline, portfolio gap, internal change,
capacity, measurement artefact, customer destination) with generic statements, signals, analyses and
response templates. The LLM uses it as a controlled vocabulary; the offline reasoner instantiates it.
Hypotheses refine into segment-specific children when evidence diverges by segment.

**Consequences.** Domain-agnostic core (enforced by test) and structural evaluation by category and
segment. Cost: questions outside "why did a volume change?" (e.g. "which capability should we invest
in?") need additional taxonomy branches — roadmap.
