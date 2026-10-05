# 0003 — Separate Source, Evidence, Claim, Finding, Recommendation, Decision

**Context.** If "a document" and "a conclusion" are the same object, provenance and uncertainty are lost
and a recommendation can quietly become a decision.

**Decision.** Distinct domain types: `Source` (what was retrieved), `Evidence` (an extracted, quoted,
quality-assessed item with hypothesis links), `Claim` (a proposition with classification and rubric),
`Finding` (a claim that met explicit promotion criteria), `StrategicOption` (an AI recommendation),
`Decision` (human-only). Hypotheses, challenges and contradictions are first-class too.

**Consequences.** Click-through provenance from option to source; classification and confidence attach
to claims, not documents; graders can check structure. Cost: more types and joins.
