"""Contextual source-quality assessment (authority tier x freshness), configured in YAML."""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import resources

import yaml
from pydantic import BaseModel, ConfigDict

from sip.domain.evidence import AuthorityTier, EvidenceNeed, Freshness, SourceQualityAssessment
from sip.domain.sources import Source, SourceType


class NeedPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: list[SourceType]
    secondary: list[SourceType]
    tertiary: list[SourceType]
    unsuitable: list[SourceType]
    current_days: int
    stale_days: int
    min_independent_sources: int = 1

    def tier_for(self, source_type: SourceType) -> AuthorityTier:
        for tier in (AuthorityTier.PRIMARY, AuthorityTier.SECONDARY, AuthorityTier.TERTIARY):
            if source_type in getattr(self, tier.value):
                return tier
        if source_type in self.unsuitable:
            return AuthorityTier.UNSUITABLE
        return AuthorityTier.TERTIARY


class SourceQualityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    needs: dict[EvidenceNeed, NeedPolicy]

    def assess(self, source: Source, need: EvidenceNeed, as_of: date) -> SourceQualityAssessment:
        policy = self.needs[need]
        tier = policy.tier_for(source.source_type)
        effective = source.effective_date
        if effective is None:
            freshness, age = Freshness.UNDATED, None
        else:
            age = (as_of - effective).days
            if age <= policy.current_days:
                freshness = Freshness.CURRENT
            elif age <= policy.stale_days:
                freshness = Freshness.AGEING
            else:
                freshness = Freshness.STALE
        rationale = (
            f"{source.source_type.value} is a {tier.value} source for {need.value} evidence; "
            + (f"dated {effective.isoformat()} ({age} days before as-of), {freshness.value}."
               if effective else "no publication date found, treated as undated.")
        )
        return SourceQualityAssessment(
            need=need, tier=tier, freshness=freshness, age_days=age, rationale=rationale
        )


@lru_cache
def default_source_quality_policy() -> SourceQualityPolicy:
    text = resources.files("sip.evidence").joinpath("source_quality.yaml").read_text()
    return SourceQualityPolicy.model_validate(yaml.safe_load(text))
