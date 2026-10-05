# Product brief

## Problem

Leadership teams regularly face questions like *"Why are enrolments falling, and what should we do?"*
The answer is rarely one cause. It is a mix of market movement, competitor moves, the organisation's own
offer, policy, and internal execution — with some of it knowable from data, some inferable, and some
genuinely unknown. Today this work is done by analysts over weeks, or skipped in favour of the most
senior person's theory.

Generic chat and RAG make this worse in a specific way: they produce fluent, confident prose that
blends evidence, inference and guesswork, cites sources that may not say what is claimed, and leaves no
record of what was considered and rejected.

## Users

| User | Needs |
|---|---|
| Investigator (strategy/insight analyst) | Decompose the question fast; see what was researched and why; add evidence |
| Privacy reviewer | Decide what confidential material the AI may see, without seeing it raw in the AI tool |
| Governance reviewer | Check options are evidenced and caveated before executives see them |
| Decision-maker | Understand the causal picture, uncertainty and trade-offs; decide; be accountable |

## Product principles

1. **Autonomous research.** The system plans and runs research, loops when evidence changes the picture,
   and stops for stated reasons.
2. **Governed reasoning.** Classification, confidence, privacy and permissions are computed by inspectable
   rules, not asserted by a model.
3. **Human decisions.** Recommendations are never decisions. Humans release sensitive data, approve
   high-consequence options, and decide.
4. **Show the uncertainty.** KNOWN / INFERRED / HYPOTHESIS / UNKNOWN on every claim; what contradicts the
   current explanation is shown next to it.
5. **Provenance or it didn't happen.** Option → finding → claim → evidence → source, always.

## Success looks like

* The planted causal structure is recovered, the planted non-causal correlation is rejected, and the
  unknowable question is labelled UNKNOWN with the missing evidence named (evaluated per scenario).
* No raw identifier reaches the agent side (evaluated).
* A decision-maker can trace any recommendation to its sources in three clicks.

## Out of scope (V1)

Decisions about individuals; executing actions; real-time data; multi-tenant SaaS operations.
