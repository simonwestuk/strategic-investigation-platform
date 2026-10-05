"""Evidence: relevant information extracted from a source, with provenance and quality."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from sip.domain.common import Actor, DomainModel, Level, new_id, utcnow


class EvidenceKind(StrEnum):
    MEASUREMENT = "measurement"  # computed or published quantitative observation
    DOCUMENTED_FACT = "documented_fact"  # a fact stated by an authoritative/first-party source
    SOURCE_ASSERTION = "source_assertion"  # a source's interpretation or opinion
    CORRELATION = "correlation"  # co-movement; never sufficient on its own for causation
    ANECDOTE = "anecdote"  # individual case (e.g. one CRM note)


class EvidenceNeed(StrEnum):
    """What the evidence is being used to establish. Source quality is judged relative to this."""

    STATISTIC = "statistic"
    POLICY = "policy"
    COMPETITOR_OFFER = "competitor_offer"
    MARKET_INTERPRETATION = "market_interpretation"
    INTERNAL_PERFORMANCE = "internal_performance"
    CUSTOMER_FEEDBACK = "customer_feedback"


class Stance(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    CONTEXT = "context"


class AuthorityTier(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNSUITABLE = "unsuitable"

    @property
    def rank(self) -> int:
        return {"primary": 3, "secondary": 2, "tertiary": 1, "unsuitable": 0}[self.value]


class Freshness(StrEnum):
    CURRENT = "current"
    AGEING = "ageing"
    STALE = "stale"
    UNDATED = "undated"


class QuoteVerification(StrEnum):
    VERIFIED = "verified"  # quote found verbatim (normalised whitespace) in the source content
    NOT_FOUND = "not_found"
    COMPUTED = "computed"  # produced by deterministic analysis; provenance is the query itself


class SourceQualityAssessment(DomainModel):
    need: EvidenceNeed
    tier: AuthorityTier
    freshness: Freshness
    age_days: int | None = None
    rationale: str


class Metric(DomainModel):
    name: str
    value: float
    unit: str = ""
    period: str | None = None
    segment: str | None = None


class HypothesisLink(DomainModel):
    hypothesis_id: str
    stance: Stance
    rationale: str = ""


class Evidence(DomainModel):
    id: str = Field(default_factory=lambda: new_id("evd"))
    source_id: str
    task_id: str | None = None
    statement: str  # normalised, self-contained statement of what the source shows
    quote: str | None = None  # verbatim span from the source, when textual
    locator: str | None = None  # paragraph index, row filter, query spec...
    kind: EvidenceKind
    need: EvidenceNeed
    observed_period: str | None = None
    observed_on: date | None = None
    relevance: Level = Level.MEDIUM
    metrics: list[Metric] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)  # entity codes this evidence concerns
    links: list[HypothesisLink] = Field(default_factory=list)
    quality: SourceQualityAssessment | None = None
    verification: QuoteVerification = QuoteVerification.NOT_FOUND
    flags: list[str] = Field(default_factory=list)
    extracted_by: Actor
    created_at: datetime = Field(default_factory=utcnow)

    def stance_for(self, hypothesis_id: str) -> Stance | None:
        for link in self.links:
            if link.hypothesis_id == hypothesis_id:
                return link.stance
        return None

    @property
    def usable(self) -> bool:
        """Evidence that may support a claim: verified/computed and not flagged as manipulated."""
        return (
            self.verification in {QuoteVerification.VERIFIED, QuoteVerification.COMPUTED}
            and "injection_suspected" not in self.flags
        )
