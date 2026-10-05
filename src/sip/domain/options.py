"""Strategic options: AI-generated *recommendations*. Never decisions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.claims import ConfidenceBand
from sip.domain.common import Actor, DomainModel, Level, new_id, utcnow


class OptionReviewStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED_FOR_DECISION = "approved_for_decision"  # cleared to be put in front of decision-makers
    MODIFIED = "modified"
    REJECTED = "rejected"


class StrategicOption(DomainModel):
    id: str = Field(default_factory=lambda: new_id("opt"))
    title: str
    description: str
    rationale: str
    finding_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    expected_benefits: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    reversibility: Level = Level.MEDIUM
    reversibility_note: str = ""
    consequence: Level = Level.MEDIUM
    additional_evidence_needed: list[str] = Field(default_factory=list)
    confidence_band: ConfidenceBand = ConfidenceBand.LOW
    review_status: OptionReviewStatus = OptionReviewStatus.DRAFT
    reviewer_note: str | None = None
    created_by: Actor
    created_at: datetime = Field(default_factory=utcnow)

    # A recommendation is never self-executing. This is a constant, not a flag to be flipped.
    @property
    def requires_human_decision(self) -> bool:
        return True
