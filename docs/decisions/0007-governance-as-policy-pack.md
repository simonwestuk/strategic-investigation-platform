# 0007 — Governance as a machine-readable policy pack

**Context.** Governance that exists only in prompts is unenforceable and unauditable.

**Decision.** A YAML policy pack listing every activity with ordered rules (conditions → autonomy,
required role, risk, consequence, reason). A small engine evaluates it; unknown activities and unmatched
attributes are denied. Every evaluation is audited with its rule ID.

**Consequences.** Policy is reviewable by non-engineers, testable, and versioned. Cost: a deliberately
simple condition language (equality, membership, ≥/≤) — enough for V1; OPA/Cedar would be the next step
if policies grow.
