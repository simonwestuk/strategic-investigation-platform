"""Ground-truth schema for evaluation scenarios."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Factor(BaseModel):
    id: str
    category: str
    segment: str | None = None
    weight: int = 1
    kind: str | None = None
    missing: str | None = None


class ContradictionMatch(BaseModel):
    hypothesis_category: str | None = None
    evidence_quote_contains: str | None = None
    evidence_source_url_contains: str | None = None


class ExpectedContradiction(BaseModel):
    id: str
    description: str
    match: ContradictionMatch


class SourceQualityTruth(BaseModel):
    stale_sources: list[str] = Field(default_factory=list)
    low_authority_sources: list[str] = Field(default_factory=list)


class InjectionTruth(BaseModel):
    source_url_contains: str | None = None
    forbidden_output_strings: list[str] = Field(default_factory=list)


class GovernanceTruth(BaseModel):
    required_reviews: list[str]
    privacy_release_must_cover: list[str] = Field(default_factory=list)
    special_category_document: str | None = None


class PrivacyTruth(BaseModel):
    sensitive_strings: list[str]


class EfficiencyTruth(BaseModel):
    max_iterations: int
    max_searches: int
    max_duplicate_task_rate: float


class GroundTruth(BaseModel):
    scenario: str
    description: str
    planted_factors: list[Factor]
    must_not_be_supported: list[Factor] = Field(default_factory=list)
    expected_unknowns: list[Factor] = Field(default_factory=list)
    expected_contradictions: list[ExpectedContradiction] = Field(default_factory=list)
    source_quality: SourceQualityTruth = Field(default_factory=SourceQualityTruth)
    injection: InjectionTruth = Field(default_factory=InjectionTruth)
    governance: GovernanceTruth
    privacy: PrivacyTruth
    efficiency: EfficiencyTruth
    thresholds: dict[str, float]


def load_ground_truth(path: Path) -> GroundTruth:
    return GroundTruth.model_validate(yaml.safe_load(path.read_text()))
