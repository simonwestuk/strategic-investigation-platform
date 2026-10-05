"""The Reasoner contract: typed inputs and outputs for every cognitive step.

Graph nodes depend on this protocol, not on a model. Two implementations exist:

* ``LLMReasoner`` - structured-output calls to the configured model provider;
* ``OfflineReasoner`` - deterministic heuristics (CI, credential-free demos, evaluation floor).

Outputs are *drafts*. Nodes validate them (cited IDs exist, quotes are verbatim, categories are in the
taxonomy), apply the confidence rubric and governance, and only then write domain entities to state.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

from sip.domain.challenges import ChallengeKind, Severity
from sip.domain.claims import Classification
from sip.domain.common import Level
from sip.domain.evidence import EvidenceKind, Stance
from sip.domain.hypotheses import Hypothesis
from sip.domain.investigation import InvestigationFrame
from sip.domain.research import AnalysisRequest, ResearchMethod
from sip.domain.sources import SourceType
from sip.models.base import ModelCall
from sip.research.text import Passage


class _Draft(BaseModel):
    model_config = {"extra": "forbid"}


# ---- inputs -------------------------------------------------------------------------------------
class EvidenceView(_Draft):
    """What a reasoner sees about one evidence item. Sanitised; no raw internal content exists here."""

    id: str
    statement: str
    kind: EvidenceKind
    need: str
    tier: str
    freshness: str
    source_title: str
    source_type: SourceType
    publisher: str | None
    dated: str | None
    stance: Stance | None = None
    segments: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)


class SourceView(_Draft):
    id: str
    title: str
    publisher: str | None
    source_type: SourceType
    dated: str | None
    url: str | None
    synthetic: bool


class PlanningContext(_Draft):
    frame: InvestigationFrame
    hypotheses: list[Hypothesis]
    completed_task_questions: list[str]
    open_research_questions: list[str]  # from challenges and humans
    datasets: list[dict[str, object]]
    has_documents: bool
    iteration: int


# ---- outputs ------------------------------------------------------------------------------------
class FrameDraft(_Draft):
    question_types: list[Literal["diagnostic", "prescriptive", "evaluative", "exploratory"]]
    subject: str
    direction: str | None
    decision_context: str
    scope: str
    out_of_scope: list[str]
    objectives: list[str]
    assumptions: list[str]
    ambiguities: list[str]
    constraints: list[str]
    needs_clarification: bool
    clarification_questions: list[str]


class HypothesisDraft(_Draft):
    category: str
    statement: str
    rationale: str
    segment: str | None = None
    would_support: list[str]
    would_contradict: list[str]
    suggested_source_types: list[SourceType]
    priority: Level


class HypothesisDrafts(_Draft):
    hypotheses: list[HypothesisDraft]


class TaskDraft(_Draft):
    question: str
    hypothesis_ids: list[str]
    method: ResearchMethod
    queries: list[str] = Field(default_factory=list)
    analysis: AnalysisRequest | None = None
    required_dataset_role: str | None = None
    required_evidence: str
    preferred_source_types: list[SourceType] = Field(default_factory=list)
    priority: Level
    expected_value: Level
    expected_value_rationale: str
    completion_criteria: str


class TaskDrafts(_Draft):
    tasks: list[TaskDraft]


class LinkDraft(_Draft):
    hypothesis_id: str
    stance: Stance
    rationale: str


class EvidenceDraft(_Draft):
    passage_index: int
    quote: str = Field(description="Exact text copied from the passage. Must appear verbatim.")
    statement: str = Field(description="Self-contained restatement of what the quote shows.")
    kind: EvidenceKind
    relevance: Level
    links: list[LinkDraft]


class EvidenceDrafts(_Draft):
    evidence: list[EvidenceDraft]


class ClaimDraft(_Draft):
    statement: str
    proposed_classification: Classification
    causal: bool
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    inferential_step: str | None
    reasoning_summary: str
    limitations: list[str]
    missing_evidence: list[str]
    next_question: str | None
    hypothesis_verdict: Literal["supports", "contradicts", "unresolved", "none"]


class ClaimDrafts(_Draft):
    claims: list[ClaimDraft]


class ChallengeDraft(_Draft):
    target_id: str
    kind: ChallengeKind
    severity: Severity
    argument: str
    research_question: str | None


class ChallengeDrafts(_Draft):
    challenges: list[ChallengeDraft]


class OptionDraft(_Draft):
    title: str
    description: str
    rationale: str
    finding_ids: list[str]
    expected_benefits: list[str]
    risks: list[str]
    uncertainties: list[str]
    dependencies: list[str]
    reversibility: Level
    reversibility_note: str
    consequence: Level
    additional_evidence_needed: list[str]


class OptionDrafts(_Draft):
    options: list[OptionDraft]


class FindingView(_Draft):
    id: str
    statement: str
    classification: Classification
    confidence_band: str
    hypothesis_categories: list[str]
    segments: list[str]


class Calls(list[ModelCall]):
    """Model calls made while producing a result (for usage and cost accounting)."""


class Reasoner(Protocol):
    name: str

    async def frame(self, question: str, organisation: str | None, context: str) -> tuple[FrameDraft, Calls]: ...

    async def hypothesise(
        self, frame: InvestigationFrame, datasets: list[dict[str, object]]
    ) -> tuple[list[HypothesisDraft], Calls]: ...

    async def plan(self, ctx: PlanningContext) -> tuple[list[TaskDraft], Calls]: ...

    async def extract(
        self, question: str, hypotheses: list[Hypothesis], source: SourceView, passages: list[Passage]
    ) -> tuple[list[EvidenceDraft], Calls]: ...

    async def draft_claims(
        self,
        frame: InvestigationFrame,
        hypothesis: Hypothesis,
        evidence: list[EvidenceView],
        blocked_reasons: list[str],
    ) -> tuple[list[ClaimDraft], Calls]: ...

    async def challenge(
        self, frame: InvestigationFrame, claims: list[dict[str, object]], evidence: list[EvidenceView]
    ) -> tuple[list[ChallengeDraft], Calls]: ...

    async def synthesise(
        self, frame: InvestigationFrame, findings: list[FindingView], unknowns: list[str], caveats: list[str]
    ) -> tuple[list[OptionDraft], Calls]: ...
