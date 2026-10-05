"""API request/response models. Responses are views over domain entities; requests never carry actors."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from sip.domain import (
    Challenge,
    Claim,
    ClassificationOverride,
    Contradiction,
    Decision,
    DecisionPayload,
    Evidence,
    Finding,
    HumanChallenge,
    HumanReview,
    Hypothesis,
    InvestigationFrame,
    ItemDecision,
    ResearchBudget,
    ResearchTask,
    ReviewAction,
    RoutingDecision,
    Source,
    StrategicOption,
    Usage,
)
from sip.privacy.models import PrivacyScanSummary


class ScenarioOut(BaseModel):
    id: str
    title: str
    organisation: str
    question: str
    datasets: int
    documents: int


class CreateInvestigation(BaseModel):
    question: str | None = Field(default=None, max_length=2000)
    scenario_id: str | None = Field(default=None, max_length=64)
    organisation: str | None = Field(default=None, max_length=200)
    context: str = Field(default="", max_length=4000)
    budget: ResearchBudget | None = None


class InvestigationSummary(BaseModel):
    id: str
    question: str
    scenario_id: str | None
    organisation: str | None
    status: str
    reasoner: str
    as_of: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class IntakeOut(BaseModel):
    id: str
    kind: str
    title: str
    filename: str
    source_type: str
    status: str
    scan: PrivacyScanSummary
    uploaded_by: str
    uploaded_at: datetime
    sanitised_preview: str


class SourceOut(Source):
    content: str | None = None


class InvestigationDetail(BaseModel):
    summary: InvestigationSummary
    frame: InvestigationFrame | None
    budget: ResearchBudget | None
    usage: Usage | None
    iteration: int
    routing: list[RoutingDecision]
    pending_review_id: str | None
    hypotheses: list[Hypothesis]
    tasks: list[ResearchTask]
    sources: list[Source]
    evidence: list[Evidence]
    claims: list[Claim]
    findings: list[Finding]
    contradictions: list[Contradiction]
    challenges: list[Challenge]
    options: list[StrategicOption]
    reviews: list[HumanReview]
    decision: Decision | None
    intake: list[IntakeOut]
    audit_count: int


class ClaimChain(BaseModel):
    """Option -> finding -> claim -> evidence -> source, for one claim."""

    claim: Claim
    evidence: list[Evidence]
    sources: list[Source]
    findings: list[Finding]
    options: list[StrategicOption]
    challenges: list[Challenge]


class ReviewResponseIn(BaseModel):
    action: ReviewAction
    note: str | None = Field(default=None, max_length=4000)
    items: list[ItemDecision] = Field(default_factory=list)
    classification_overrides: list[ClassificationOverride] = Field(default_factory=list)
    challenges: list[HumanChallenge] = Field(default_factory=list)
    research_requests: list[str] = Field(default_factory=list, max_length=10)
    option_edits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    decision: DecisionPayload | None = None
    additional_iterations: int = Field(default=0, ge=0, le=3)


class AuditOut(BaseModel):
    id: str
    at: datetime
    actor_kind: str
    actor_id: str
    action: str
    subject_type: str | None
    subject_id: str | None
    policy_rule_id: str | None
    summary: str
    details: dict[str, Any]
