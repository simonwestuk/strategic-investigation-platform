"""Loader for the generic driver taxonomy (see taxonomy.yaml)."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources

import yaml
from pydantic import BaseModel, ConfigDict, Field

from sip.domain.common import Level
from sip.domain.evidence import EvidenceNeed
from sip.domain.sources import SourceType


class Signals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    support: list[str] = Field(default_factory=list)
    contradict: list[str] = Field(default_factory=list)


class DriverCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    statement: str
    segment_statement: str | None = None
    rationale: str
    priority: Level
    would_support: list[str]
    would_contradict: list[str]
    source_types: list[SourceType]
    evidence_need: EvidenceNeed
    analyses: list[str] = Field(default_factory=list)
    web_queries: list[str] = Field(default_factory=list)
    document_queries: list[str] = Field(default_factory=list)
    supported_by: list[str] = Field(default_factory=list)
    contradicted_by: list[str] = Field(default_factory=list)
    split_by_entity: bool = False
    requires_dataset_role: str | None = None
    signals: Signals = Field(default_factory=Signals)


class ResponseTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    reversibility: Level
    consequence: Level


class Taxonomy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    categories: dict[str, DriverCategory]
    responses: dict[str, ResponseTemplate] = Field(default_factory=dict)

    def stance_for_pattern(self, category: str, pattern_code: str) -> str | None:
        c = self.categories.get(category)
        if c is None:
            return None
        if pattern_code in c.supported_by:
            return "supports"
        if pattern_code in c.contradicted_by:
            return "contradicts"
        return None


@lru_cache
def default_taxonomy() -> Taxonomy:
    text = resources.files("sip.agents").joinpath("taxonomy.yaml").read_text()
    return Taxonomy.model_validate(yaml.safe_load(text))
