from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimStatus(StrEnum):
    KNOWN = "known"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"


class EvidenceDirection(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class SourceKind(StrEnum):
    PUBLIC_WEB = "public_web"
    INTERNAL_DOCUMENT = "internal_document"
    INTERNAL_STRUCTURED = "internal_structured"
    USER_INPUT = "user_input"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    INVESTIGATE_FURTHER = "investigate_further"


class Source(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    kind: SourceKind
    title: str
    publisher: str | None = None
    url: HttpUrl | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    sensitivity: Sensitivity = Sensitivity.PUBLIC
    authority_score: float = Field(default=0.5, ge=0, le=1)
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    statement: str
    direction: EvidenceDirection = EvidenceDirection.CONTEXT
    relevance: float = Field(default=0.5, ge=0, le=1)
    extraction_confidence: float = Field(default=0.5, ge=0, le=1)
    locator: str | None = None


class Hypothesis(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    statement: str
    rationale: str
    status: ClaimStatus = ClaimStatus.HYPOTHESIS
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence_needed: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)


class Claim(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    statement: str
    status: ClaimStatus
    confidence: float = Field(ge=0, le=1)
    supporting_evidence_ids: list[UUID] = Field(default_factory=list)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)


class ResearchTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    question: str
    rationale: str
    preferred_source_kinds: list[SourceKind] = Field(default_factory=list)
    completed: bool = False


class DecisionOption(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    expected_impact: str | None = None
    risks: list[str] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    requires_human_decision: bool = True


class HumanReview(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    reason: str
    risk_level: RiskLevel
    requested_at: datetime = Field(default_factory=utcnow)
    decision: ReviewDecision | None = None
    reviewer_note: str | None = None
    decided_at: datetime | None = None


class Investigation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    question: str
    scope: str | None = None
    decision_context: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    research_tasks: list[ResearchTask] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    decision_options: list[DecisionOption] = Field(default_factory=list)
    human_reviews: list[HumanReview] = Field(default_factory=list)
