"""Append-only audit events. Details must never contain raw confidential content."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sip.domain.common import Actor, DomainModel, new_id, utcnow


class AuditAction(StrEnum):
    INVESTIGATION_CREATED = "investigation_created"
    QUESTION_FRAMED = "question_framed"
    POLICY_EVALUATED = "policy_evaluated"
    DOCUMENT_SCANNED = "document_scanned"
    DOCUMENT_RELEASED = "document_released"
    DOCUMENT_WITHHELD = "document_withheld"
    HYPOTHESIS_CREATED = "hypothesis_created"
    HYPOTHESIS_UPDATED = "hypothesis_updated"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_SKIPPED = "task_skipped"
    SOURCE_ADDED = "source_added"
    INJECTION_FLAGGED = "injection_flagged"
    EVIDENCE_ADDED = "evidence_added"
    CLAIM_CLASSIFIED = "claim_classified"
    CLAIM_DOWNGRADED = "claim_downgraded"
    CLAIM_OVERRIDDEN = "claim_overridden"
    FINDING_PROMOTED = "finding_promoted"
    CHALLENGE_RAISED = "challenge_raised"
    CHALLENGE_RESOLVED = "challenge_resolved"
    ROUTING_DECISION = "routing_decision"
    OPTION_GENERATED = "option_generated"
    REVIEW_REQUESTED = "review_requested"
    REVIEW_RESOLVED = "review_resolved"
    DECISION_RECORDED = "decision_recorded"
    ACTION_REFUSED = "action_refused"


class AuditEvent(DomainModel):
    id: str = Field(default_factory=lambda: new_id("aud"))
    at: datetime = Field(default_factory=utcnow)
    actor: Actor
    action: AuditAction
    subject_type: str | None = None
    subject_id: str | None = None
    summary: str
    policy_rule_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
