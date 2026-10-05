"""Sceptic challenges and contradictions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.common import Actor, DomainModel, new_id, utcnow
from sip.domain.research import AnalysisRequest


class ChallengeKind(StrEnum):
    UNSUPPORTED = "unsupported_by_evidence"
    CORRELATION_NOT_CAUSATION = "correlation_not_causation"
    IGNORED_CONTRADICTION = "ignored_contradiction"
    STALE_EVIDENCE = "stale_evidence"
    WEAK_SOURCE = "weak_source"
    OVERGENERALISATION = "overgeneralisation"
    HYPOTHESIS_AS_FINDING = "hypothesis_presented_as_finding"
    ALTERNATIVE_EXPLANATION = "alternative_explanation"
    MATERIAL_GAP = "material_gap"
    PREMATURE_CONVERGENCE = "premature_convergence"
    INJECTION_SUSPECTED = "injection_suspected"
    HUMAN_CHALLENGE = "human_challenge"


class Severity(StrEnum):
    BLOCKING = "blocking"
    MAJOR = "major"
    MINOR = "minor"


class ChallengeStatus(StrEnum):
    OPEN = "open"
    ADDRESSED = "addressed"  # further research or reclassification resolved it
    ACCEPTED_AS_LIMITATION = "accepted_as_limitation"  # recorded as a caveat (e.g. budget spent)
    DISMISSED_BY_HUMAN = "dismissed_by_human"


class Challenge(DomainModel):
    id: str = Field(default_factory=lambda: new_id("chl"))
    target_type: str  # "claim" | "hypothesis" | "finding" | "investigation"
    target_id: str
    kind: ChallengeKind
    severity: Severity
    argument: str
    research_question: str | None = None  # when set, the challenger is asking for more research
    suggested_analysis: AnalysisRequest | None = None  # a concrete disconfirming test, if one exists
    research_attempted: bool = False
    status: ChallengeStatus = ChallengeStatus.OPEN
    resolution_note: str | None = None
    raised_by: Actor
    iteration: int = 0
    created_at: datetime = Field(default_factory=utcnow)


class ContradictionStatus(StrEnum):
    UNRESOLVED = "unresolved"
    RESOLVED_BY_SOURCE_QUALITY = "resolved_by_source_quality"
    EXPLAINED = "explained"
    RESOLVED_BY_HUMAN = "resolved_by_human"


class Contradiction(DomainModel):
    id: str = Field(default_factory=lambda: new_id("ctr"))
    description: str
    hypothesis_id: str | None = None
    claim_id: str | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    status: ContradictionStatus = ContradictionStatus.UNRESOLVED
    resolution_note: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
