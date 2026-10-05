"""Privacy gateway data types.

Two families of types live here and must not be confused:

* ``Detection`` carries raw entity values. It exists only *inside* the gateway and is never
  serialised outside it (it is a dataclass, deliberately not a Pydantic domain model).
* ``PrivacyScanSummary`` / ``IntakeDocument`` are the sanitised outputs that may cross the boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.classification import DataClassification
from sip.domain.common import DomainModel, new_id, utcnow
from sip.domain.sources import SourceType


class EntityType(StrEnum):
    PERSON = "PERSON"
    STAFF = "STAFF"
    EMPLOYER = "EMPLOYER"  # third-party organisation (customer, client, employer)
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    POSTCODE = "POSTCODE"
    NATIONAL_ID = "NATIONAL_ID"
    SPECIAL_CATEGORY = "SPECIAL_CATEGORY"

    @property
    def is_personal(self) -> bool:
        return self not in {EntityType.EMPLOYER}


@dataclass(frozen=True)
class Detection:
    entity_type: EntityType
    start: int
    end: int
    text: str  # RAW VALUE - never leaves the gateway
    confidence: float
    detector: str
    subcategory: str | None = None


LOW_CONFIDENCE = 0.75


class EntityCount(DomainModel):
    entity_type: EntityType
    count: int
    low_confidence: int = 0


class PrivacyScanSummary(DomainModel):
    """What a reviewer (and the agent boundary) may know about a scan: counts and categories only."""

    detector: str
    entity_counts: list[EntityCount] = Field(default_factory=list)
    low_confidence_detections: int = 0
    special_category_spans: int = 0
    special_category_types: list[str] = Field(default_factory=list)
    confidentiality_markers: list[str] = Field(default_factory=list)
    classification: DataClassification
    declared_classification: DataClassification
    pseudonym_tokens: int = 0


class IntakeStatus(StrEnum):
    PENDING_RELEASE = "pending_release"
    RELEASED = "released"
    WITHHELD = "withheld"  # prohibited by policy
    REJECTED = "rejected"  # rejected by a human reviewer


class IntakeKind(StrEnum):
    DOCUMENT = "document"
    DATASET = "dataset"


class IntakeDocument(DomainModel):
    """A sanitised candidate for release across the privacy boundary."""

    id: str = Field(default_factory=lambda: new_id("doc"))
    investigation_id: str | None = None
    kind: IntakeKind = IntakeKind.DOCUMENT
    title: str
    filename: str
    content_type: str
    source_type: SourceType
    sha256: str  # hash of the RAW content, for integrity/dedupe; not reversible
    size_bytes: int
    sanitised_text: str
    scan: PrivacyScanSummary
    status: IntakeStatus = IntakeStatus.PENDING_RELEASE
    status_reason: str | None = None
    dataset_id: str | None = None
    published_on: str | None = None
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=utcnow)
