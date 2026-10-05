from __future__ import annotations

from sip.domain.models import Claim, ClaimStatus, DecisionOption, Hypothesis, ResearchTask
from sip.governance.policy import assess_investigation
from sip.graph.state import InvestigationState


async def frame_investigation(state: InvestigationState) -> dict:
    inv = state["investigation"].model_copy(deep=True)
    if not inv.scope:
        inv.scope = "Establish plausible causes, evidence gaps, and decision options without treating inference as fact."
    return {"investigation": inv}


async def generate_hypotheses(state: InvestigationState) -> dict:
    """Deterministic seed for the flagship scenario; later supplied by the model provider."""
    inv = state["investigation"].model_copy(deep=True)
    if not inv.hypotheses:
        seeds = [
            ("Overall market demand has declined.", "Separate market contraction from provider-specific performance."),
            ("The provider is losing market share to competitors.", "Competitor switching may explain decline beyond the market."),
            ("The programme proposition is less attractive than alternatives.", "Duration, currency, delivery and assessment may create friction."),
            ("Demand is migrating to newer AI-focused apprenticeships.", "New AI pathways may substitute for general digital programmes."),
            ("Funding or policy changes have changed employer demand.", "Level-specific funding changes can alter purchasing behaviour."),
            ("Internal funnel conversion has deteriorated.", "Demand may exist but be lost between opportunity, application and enrolment."),
        ]
        inv.hypotheses = [Hypothesis(statement=s, rationale=r) for s, r in seeds]
    return {"investigation": inv}


async def plan_research(state: InvestigationState) -> dict:
    inv = state["investigation"].model_copy(deep=True)
    if not inv.research_tasks:
        inv.research_tasks = [
            ResearchTask(question=f"What evidence would support or contradict: {h.statement}", rationale=h.rationale)
            for h in inv.hypotheses
        ]
    return {"investigation": inv}


async def gather_evidence(state: InvestigationState) -> dict:
    # Tool adapters will populate sources/evidence. Keeping the node real and testable before credentials exist.
    inv = state["investigation"].model_copy(deep=True)
    return {"investigation": inv, "iteration": state["iteration"] + 1}


async def analyse(state: InvestigationState) -> dict:
    inv = state["investigation"].model_copy(deep=True)
    if not inv.claims:
        inv.claims.append(
            Claim(
                statement="The investigation does not yet contain enough evidence to establish a primary cause.",
                status=ClaimStatus.UNKNOWN,
                confidence=1.0,
                limitations=["External research and internal evidence adapters are not yet populated."],
                next_questions=["Collect evidence for each active hypothesis."],
            )
        )
    return {"investigation": inv}


async def challenge(state: InvestigationState) -> dict:
    inv = state["investigation"].model_copy(deep=True)
    unsupported = [c.statement for c in inv.claims if c.status == ClaimStatus.INFERRED and not c.supporting_evidence_ids]
    inv.contradictions.extend(f"Unsupported inference: {item}" for item in unsupported)
    needs_more = state["iteration"] < state["max_iterations"] and not inv.evidence
    return {"investigation": inv, "needs_more_research": needs_more}


async def synthesise(state: InvestigationState) -> dict:
    inv = state["investigation"].model_copy(deep=True)
    if not inv.decision_options:
        inv.decision_options = [
            DecisionOption(
                title="Continue investigation",
                description="Do not make a portfolio intervention until the key hypotheses have evidence.",
                risks=["Delay may have opportunity cost."],
            )
        ]
    return {"investigation": inv}


async def governance_gate(state: InvestigationState) -> dict:
    assessment = assess_investigation(state["investigation"])
    return {"requires_human_review": assessment.requires_human_review}
