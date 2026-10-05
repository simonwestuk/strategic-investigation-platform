# 0006 — Decision is human-only

**Context.** The most dangerous failure for a decision-support system is an AI recommendation silently
becoming an organisational decision.

**Decision.** `Decision` validates human actor + `decision_maker` role + acknowledged uncertainty. It is
constructed only in `await_review` from a resumed `DECISION` interrupt whose actor is injected by the
authenticated API (request bodies cannot carry an actor). Policy marks `record_decision` human-only.

**Consequences.** Defence in depth across type, graph, API and policy; tested at each layer. Cost: a
decision always needs a resume round-trip through the graph.
