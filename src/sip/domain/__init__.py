"""Domain model. Pure Pydantic; no I/O, no framework imports."""

from sip.domain.audit import AuditAction, AuditEvent
from sip.domain.challenges import (
    Challenge,
    ChallengeKind,
    ChallengeStatus,
    Contradiction,
    ContradictionStatus,
    Severity,
)
from sip.domain.claims import (
    Claim,
    Classification,
    ConfidenceAssessment,
    ConfidenceBand,
    Finding,
    FindingStatus,
    HumanOverride,
    ReviewState,
)
from sip.domain.classification import Confidentiality, DataClassification, PersonalData
from sip.domain.common import Actor, ActorKind, Level, Role, new_id, utcnow
from sip.domain.decisions import Decision, DecisionType
from sip.domain.evidence import (
    AuthorityTier,
    Evidence,
    EvidenceKind,
    EvidenceNeed,
    Freshness,
    HypothesisLink,
    Metric,
    QuoteVerification,
    SourceQualityAssessment,
    Stance,
)
from sip.domain.hypotheses import Hypothesis, HypothesisOrigin, HypothesisStatus
from sip.domain.investigation import InvestigationFrame, InvestigationStatus, QuestionType
from sip.domain.options import OptionReviewStatus, StrategicOption
from sip.domain.research import (
    AnalysisRequest,
    ResearchBudget,
    ResearchMethod,
    ResearchTask,
    RoutingDecision,
    StopReason,
    TaskOrigin,
    TaskStatus,
    Usage,
)
from sip.domain.reviews import (
    ClassificationOverride,
    DecisionPayload,
    HumanChallenge,
    HumanReview,
    ItemDecision,
    ReviewAction,
    ReviewKind,
    ReviewResponse,
    ReviewStatus,
)
from sip.domain.sources import RetrievalMethod, Source, SourceOrigin, SourceType

__all__ = [
    "Actor", "ActorKind", "AnalysisRequest", "AuditAction", "AuditEvent", "AuthorityTier",
    "Challenge", "ChallengeKind", "ChallengeStatus", "Claim", "Classification",
    "ClassificationOverride", "ConfidenceAssessment", "ConfidenceBand", "Confidentiality",
    "Contradiction", "ContradictionStatus", "DataClassification", "Decision", "DecisionPayload",
    "DecisionType", "Evidence", "EvidenceKind", "EvidenceNeed", "Finding", "FindingStatus",
    "Freshness", "HumanChallenge", "HumanOverride", "HumanReview", "Hypothesis", "HypothesisLink",
    "HypothesisOrigin", "HypothesisStatus", "InvestigationFrame", "InvestigationStatus",
    "ItemDecision", "Level", "Metric", "OptionReviewStatus", "PersonalData", "QuestionType",
    "QuoteVerification", "ResearchBudget", "ResearchMethod", "ResearchTask", "RetrievalMethod",
    "ReviewAction", "ReviewKind", "ReviewResponse", "ReviewState", "ReviewStatus", "Role",
    "RoutingDecision", "Severity", "Source", "SourceOrigin", "SourceQualityAssessment",
    "SourceType", "Stance", "StopReason", "StrategicOption", "TaskOrigin", "TaskStatus", "Usage",
    "new_id", "utcnow",
]
