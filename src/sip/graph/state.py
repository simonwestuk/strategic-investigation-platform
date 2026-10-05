"""Typed LangGraph state.

Entity collections are ``dict[id, Model]`` channels with a merge reducer so that parallel research
branches (``Send`` fan-out) can each contribute sources/evidence without overwriting one another.
Audit events and routing decisions are append-only. Usage is summed.
"""

from __future__ import annotations

import operator
from datetime import date
from typing import Annotated, Any, TypedDict

from pydantic import BaseModel, Field

from sip.domain import (
    AuditEvent,
    Challenge,
    Claim,
    Contradiction,
    Decision,
    Evidence,
    Finding,
    HumanReview,
    Hypothesis,
    InvestigationFrame,
    ResearchBudget,
    ResearchTask,
    RoutingDecision,
    Source,
    StrategicOption,
    Usage,
)


def merge(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    return {**(left or {}), **(right or {})}


def add_usage(left: Usage | None, right: Usage | None) -> Usage:
    return (left or Usage()) + (right or Usage())


RESET = "__reset__"


class ResearchOutput(BaseModel):
    """What one research branch produced. Staged, then deduplicated by the evidence manager."""

    task: ResearchTask
    sources: list[Source] = Field(default_factory=list)
    documents: dict[str, str] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    duplicates_skipped: int = 0


def staged(left: list[ResearchOutput] | None, right: list[ResearchOutput] | str | None) -> list[ResearchOutput]:
    if right == RESET:
        return []
    return [*(left or []), *(right if isinstance(right, list) else [])]


class InvestigationState(TypedDict, total=False):
    # identity and input
    investigation_id: str
    scenario_id: str | None
    question: str
    organisation: str | None
    context: str
    as_of: date
    reasoner: str

    # framing and control
    frame: InvestigationFrame | None
    budget: ResearchBudget
    iteration: int
    round_task_ids: list[str]
    next_after_review: str | None
    pending_review_id: str | None
    research_requests: list[str]
    staging: Annotated[list[ResearchOutput], staged]

    # privacy boundary: sanitised material only
    intake_status: Annotated[dict[str, str], merge]  # intake document id -> IntakeStatus
    released_dataset_ids: Annotated[dict[str, str], merge]  # dataset id -> source id
    documents: Annotated[dict[str, str], merge]  # source id -> sanitised text

    # investigation entities
    hypotheses: Annotated[dict[str, Hypothesis], merge]
    tasks: Annotated[dict[str, ResearchTask], merge]
    sources: Annotated[dict[str, Source], merge]
    evidence: Annotated[dict[str, Evidence], merge]
    claims: Annotated[dict[str, Claim], merge]
    findings: Annotated[dict[str, Finding], merge]
    contradictions: Annotated[dict[str, Contradiction], merge]
    challenges: Annotated[dict[str, Challenge], merge]
    options: Annotated[dict[str, StrategicOption], merge]
    reviews: Annotated[dict[str, HumanReview], merge]
    decision: Decision | None

    # telemetry
    routing: Annotated[list[RoutingDecision], operator.add]
    audit: Annotated[list[AuditEvent], operator.add]
    usage: Annotated[Usage, add_usage]
