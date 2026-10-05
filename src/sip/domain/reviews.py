"""Human reviews: the record of every human-in-the-loop interrupt and its response."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sip.domain.claims import Classification
from sip.domain.common import Actor, DomainModel, Role, new_id, utcnow


class ReviewKind(StrEnum):
    CLARIFICATION = "clarification"
    PRIVACY_RELEASE = "privacy_release"
    FINDINGS = "findings"
    OPTIONS = "options"
    DECISION = "decision"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    RESOLVED = "resolved"


class ReviewAction(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    REQUEST_FURTHER_INVESTIGATION = "request_further_investigation"
    DECIDE = "decide"  # only valid for DECISION reviews


class ClassificationOverride(DomainModel):
    claim_id: str
    classification: Classification
    reason: str


class HumanChallenge(DomainModel):
    target_id: str  # claim / hypothesis / finding id, or the investigation id for assumptions
    argument: str


class ItemDecision(DomainModel):
    """Per-item response inside a batch review (e.g. one document in a privacy review)."""

    item_id: str
    action: ReviewAction
    note: str | None = None


class DecisionPayload(DomainModel):
    decision_type: str
    statement: str
    rationale: str
    option_ids: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    uncertainties_acknowledged: bool = False
    acknowledged_unknown_claim_ids: list[str] = Field(default_factory=list)


class ReviewResponse(DomainModel):
    action: ReviewAction
    note: str | None = None
    actor: Actor  # populated by the API from the authenticated principal
    items: list[ItemDecision] = Field(default_factory=list)
    classification_overrides: list[ClassificationOverride] = Field(default_factory=list)
    challenges: list[HumanChallenge] = Field(default_factory=list)
    research_requests: list[str] = Field(default_factory=list)
    option_edits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    decision: DecisionPayload | None = None
    additional_iterations: int = Field(default=0, ge=0, le=3)
    responded_at: datetime = Field(default_factory=utcnow)


class HumanReview(DomainModel):
    id: str = Field(default_factory=lambda: new_id("rev"))
    kind: ReviewKind
    title: str
    reason: str
    subject_ids: list[str] = Field(default_factory=list)
    policy_rule_ids: list[str] = Field(default_factory=list)
    required_role: Role
    allowed_actions: list[ReviewAction]
    context: dict[str, Any] = Field(default_factory=dict)  # sanitised summary shown to the reviewer
    status: ReviewStatus = ReviewStatus.PENDING
    requested_at: datetime = Field(default_factory=utcnow)
    response: ReviewResponse | None = None
