"""Claims and findings.

A *claim* is any proposition the investigation makes, classified as KNOWN / INFERRED / HYPOTHESIS /
UNKNOWN. A *finding* is a claim that has met explicit promotion criteria. Classification and confidence
are computed by a transparent rubric (``sip.evidence.confidence``); the model's proposal is kept for audit.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.common import Actor, DomainModel, new_id, utcnow


class Classification(StrEnum):
    KNOWN = "known"
    INFERRED = "inferred"
    HYPOTHESIS = "hypothesis"
    UNKNOWN = "unknown"

    @property
    def strength(self) -> int:
        return {"known": 3, "inferred": 2, "hypothesis": 1, "unknown": 0}[self.value]


class ConfidenceBand(StrEnum):
    """Ordinal band, NOT a probability. See docs/evaluation.md#confidence."""

    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    VERY_LOW = "very_low"


class ConfidenceAssessment(DomainModel):
    band: ConfidenceBand
    score: int  # rubric points; only meaningful relative to the rubric that produced it
    factors: list[str] = Field(default_factory=list)  # human-readable contributions (+2 primary...)
    classification_ceiling: Classification
    ceiling_reasons: list[str] = Field(default_factory=list)


class ReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    CHALLENGED = "challenged"
    ACCEPTED = "accepted"
    OVERRIDDEN = "overridden"
    REJECTED = "rejected"


class HumanOverride(DomainModel):
    actor: Actor
    previous: Classification
    new: Classification
    reason: str
    at: datetime = Field(default_factory=utcnow)


class Claim(DomainModel):
    id: str = Field(default_factory=lambda: new_id("clm"))
    statement: str
    classification: Classification
    proposed_classification: Classification  # what the reasoner proposed before the rubric
    confidence: ConfidenceAssessment | None = None
    causal: bool = False  # asserts that something *causes* something
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    source_quality_summary: str = ""
    reasoning_summary: str = ""
    inferential_step: str | None = None
    limitations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    related_hypothesis_ids: list[str] = Field(default_factory=list)
    next_question: str | None = None
    created_by: Actor
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    review_state: ReviewState = ReviewState.UNREVIEWED
    human_override: HumanOverride | None = None
    iteration: int = 0
    # False when a later analysis round no longer produces this claim (kept for audit history).
    active: bool = True


class FindingStatus(StrEnum):
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Finding(DomainModel):
    """A conclusion sufficiently supported under defined criteria (see ``promotion_criteria``)."""

    id: str = Field(default_factory=lambda: new_id("fnd"))
    title: str
    statement: str
    claim_ids: list[str]
    hypothesis_ids: list[str] = Field(default_factory=list)
    classification: Classification
    confidence_band: ConfidenceBand
    criteria_met: list[str] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.DRAFT
    created_at: datetime = Field(default_factory=utcnow)
