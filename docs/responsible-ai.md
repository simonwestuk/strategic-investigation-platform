# Responsible AI

Each section states the risk, the control *in this codebase*, and what remains the deployer's
responsibility. Generic statements without a corresponding control are deliberately omitted.

## Intended use

Decision **support** for strategic investigations in an organisation: decomposing an ambiguous question,
gathering and weighing evidence, exposing uncertainty, and preparing options for accountable people.

## Not intended for

* Decisions about individuals (employment, performance, eligibility, credit, admissions). The policy
  prohibits agent analysis of row-level personal data; special-category content is withheld.
* Automated execution of decisions (`take_external_action` is prohibited for everyone).
* Producing authoritative facts about the world without review. Outputs are classified claims with
  provenance, not answers.
* Public-sector or regulated decisions where an approved impact assessment has not been carried out.

## Human responsibility

Only an authenticated human with `decision_maker` can create a Decision; the decision-maker must
acknowledge stated uncertainties, and the decision links to the review it resolved
([governance.md](governance.md#recommendation--decision)). Options are labelled as AI recommendations in
the API and UI. High-consequence options must pass a governance reviewer before reaching decision-makers.

## Evidence limitations

* Every promoted claim cites evidence; every textual evidence item has a verbatim quote checked against
  the stored source; every computed item records the analytical query that produced it.
* Classification is capped by the confidence rubric: causal claims are at most INFERRED; correlation-only
  causal claims at most HYPOTHESIS; contradicted claims at most HYPOTHESIS.
* Unavailable evidence is recorded as such (`blocked_unavailable` tasks, UNKNOWN claims with the missing
  evidence named) rather than filled by inference.

## Model limitations

* LLM outputs are treated as drafts: IDs validated, quotes verified, categories constrained,
  classifications capped, arithmetic done in code.
* Stance assignment (does this quote support or contradict?) is model or heuristic judgement and is not
  independently verified. The challenger, rubric and evaluation mitigate but do not eliminate this.
* The offline reasoner is a deterministic baseline, not an intelligent agent; its Northstar and
  Harbourline results reflect shared deterministic machinery working on well-structured synthetic data.

## Confidence

Confidence is an ordinal band from a published rubric (`sip/evidence/confidence.py`), not a probability.
Every claim shows its factors (e.g. "+3 best supporting source is primary tier", "−2 contradicted by
equal-or-stronger evidence") and ceiling reasons. Model self-reported confidence is not used.

## Hallucination

Controls: no free-text answer path; structured outputs only; cited IDs must exist (dropped otherwise, and
noted in the claim's limitations); quotes must be verbatim; numbers in claims must appear in cited evidence
(`grounding_numeric` grader); the sceptic raises `unsupported_by_evidence` for claims without usable
evidence.

## Bias and source bias

* Source authority is contextual (a competitor's own page is primary for its own offer, unsuitable for
  market statistics) and configured in `source_quality.yaml`, reviewable by the organisation.
* Freshness is relative to the investigation's as-of date; stale sources cannot alone support a promoted
  claim (`source_quality` grader).
* Independence: many items from one publisher count once.
* Hypothesis generation starts from a broad, generic driver taxonomy, including explanations that are
  uncomfortable for leadership (internal change, offer quality, conversion), to counter
  confirmation bias in the question.
* Residual: web search ranking and corpus coverage bias what is found. The research activity view
  shows what was searched and why, so reviewers can see gaps.

## Automation bias

* The Decision Room leads with *what we know / infer / do not know / what contradicts*, not with a
  recommended answer.
* Options include a "commission research on unknowns" option and a do-nothing baseline.
* Decisions require explicit acknowledgement of each UNKNOWN.
* The challenger's open challenges and accepted limitations are shown next to the conclusions they
  affect.

## High-consequence decisions

`present_recommendation` requires governance review for high-consequence options or low-confidence
evidence. Reversibility and consequence are recorded on every option.

## Auditability and contestability

* Audit trail: every policy evaluation, release, classification change, challenge, routing decision,
  review and decision, with actor and policy rule.
* Click-through provenance: option → finding → claim → evidence → source (API `GET /claims/{id}` and the
  UI claim drawer).
* Contest: any reviewer can challenge a claim or assumption (creating research), override a
  classification with a recorded reason (governance role), reject options, or send the investigation
  back for further research.

## Privacy

See [privacy.md](privacy.md). Summary: gateway before agent boundary, pseudonymisation preserving
linkage, special-category withholding, separate encrypted vault, human release review for sensitive
material, leakage evaluation over all agent-visible state.

## Data retention

V1 implements no automated deletion. Deployers must define retention for: quarantine (raw uploads), the
vault, the application database, checkpoints, LangSmith traces (project retention settings) and
Application Insights. Roadmap: per-investigation retention policy with cascade deletion (the schema
already cascades from `investigations`) and vault entry expiry.

## Security

See [threat-model.md](threat-model.md).

## Before using with real data

1. Complete a DPIA; confirm lawful basis for processing personal data in internal documents.
2. Switch to Azure AI Language for PII detection; keep human release review for confidential material.
3. Configure Entra ID app roles and assign them deliberately (privacy reviewer ≠ decision-maker).
4. Review and adapt the policy pack and source-quality policy with governance and domain owners.
5. Build a scenario from your own historical decisions with known outcomes and run the evaluation.
