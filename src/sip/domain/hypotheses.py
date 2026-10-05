"""Hypotheses: propositions actively being investigated, organised as a tree."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.common import DomainModel, Level, new_id, utcnow
from sip.domain.sources import SourceType


class HypothesisStatus(StrEnum):
    PROPOSED = "proposed"
    INVESTIGATING = "investigating"
    SUPPORTED = "supported"
    WEAKENED = "weakened"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"  # cannot be resolved with available evidence
    SPLIT = "split"  # refined into segment-specific child hypotheses


class HypothesisOrigin(StrEnum):
    INITIAL = "initial"
    EMERGENT = "emergent"  # created because evidence changed the investigation
    CHALLENGER = "challenger"
    HUMAN = "human"


class Hypothesis(DomainModel):
    id: str = Field(default_factory=lambda: new_id("hyp"))
    statement: str
    rationale: str
    category: str  # driver category id from the generic driver taxonomy
    segment: str | None = None  # None = applies to the whole subject
    parent_id: str | None = None
    origin: HypothesisOrigin = HypothesisOrigin.INITIAL
    would_support: list[str] = Field(default_factory=list)
    would_contradict: list[str] = Field(default_factory=list)
    suggested_source_types: list[SourceType] = Field(default_factory=list)
    priority: Level = Level.MEDIUM
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    status_reason: str = ""
    created_from_evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def is_open(self) -> bool:
        return self.status in {HypothesisStatus.PROPOSED, HypothesisStatus.INVESTIGATING}
