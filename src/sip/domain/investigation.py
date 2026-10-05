"""Investigation-level objects: the framed question and lifecycle status."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field

from sip.domain.common import DomainModel


class InvestigationStatus(StrEnum):
    DRAFT = "draft"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    AWAITING_DECISION = "awaiting_decision"
    DECIDED = "decided"
    FAILED = "failed"


class QuestionType(StrEnum):
    DIAGNOSTIC = "diagnostic"  # why did X happen?
    PRESCRIPTIVE = "prescriptive"  # what should we do?
    EVALUATIVE = "evaluative"  # should we do X?
    EXPLORATORY = "exploratory"


class InvestigationFrame(DomainModel):
    """The Investigation Lead's output. It frames the problem; it does not try to answer it."""

    question: str
    question_types: list[QuestionType]
    subject: str  # what is being explained, e.g. "degree-apprenticeship enrolments"
    organisation: str | None = None
    direction: str | None = None  # "decline", "increase", ...
    decision_context: str
    scope: str
    out_of_scope: list[str] = Field(default_factory=list)
    objectives: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    as_of: date
