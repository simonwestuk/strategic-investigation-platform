"""Sources: things that were retrieved, uploaded or queried. A source is not evidence."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.classification import DataClassification
from sip.domain.common import DomainModel, new_id, utcnow


class SourceOrigin(StrEnum):
    EXTERNAL_WEB = "external_web"
    INTERNAL = "internal"
    HUMAN = "human"


class SourceType(StrEnum):
    """What kind of publisher/artefact a source is. Authority is *not* stored here: it depends on
    what the evidence is being used for (see ``sip.evidence.source_quality``)."""

    OFFICIAL_STATISTICS = "official_statistics"
    GOVERNMENT_POLICY = "government_policy"
    REGULATOR = "regulator"
    STANDARDS_BODY = "standards_body"
    INDUSTRY_BODY = "industry_body"
    ACADEMIC = "academic"
    COMPETITOR_OFFICIAL = "competitor_official"
    ORGANISATION_OFFICIAL = "organisation_official"
    NEWS = "news"
    TRADE_PRESS = "trade_press"
    COMMENTARY = "commentary"
    INTERNAL_DATASET = "internal_dataset"
    INTERNAL_DOCUMENT = "internal_document"
    CRM_RECORD = "crm_record"
    HUMAN_SUPPLIED = "human_supplied"
    UNKNOWN = "unknown"


class RetrievalMethod(StrEnum):
    WEB_SEARCH = "web_search"
    DIRECT_FETCH = "direct_fetch"
    UPLOAD = "upload"
    DATASET_QUERY = "dataset_query"
    SCENARIO_FIXTURE = "scenario_fixture"


class Source(DomainModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    origin: SourceOrigin
    source_type: SourceType
    title: str
    publisher: str | None = None
    canonical_url: str | None = None
    domain: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    published_on: date | None = None
    updated_on: date | None = None
    content_hash: str | None = None
    classification: DataClassification = Field(default_factory=DataClassification)
    retrieval_method: RetrievalMethod
    retrieval_provider: str | None = None  # e.g. "tavily", "offline_corpus", "privacy_gateway"
    discovered_by_task_id: str | None = None
    # True for content that is part of a synthetic scenario (never presented as real-world fact).
    synthetic: bool = False
    # Defensive screening results for untrusted content (see sip.research.injection).
    injection_flags: list[str] = Field(default_factory=list)
    privacy_document_id: str | None = None  # link to the privacy gateway record for internal docs

    @property
    def effective_date(self) -> date | None:
        return self.updated_on or self.published_on
