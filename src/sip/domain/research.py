"""Research tasks, analysis requests, budgets and usage."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from sip.domain.common import DomainModel, Level, new_id, utcnow
from sip.domain.sources import SourceType


class ResearchMethod(StrEnum):
    WEB_SEARCH = "web_search"
    INTERNAL_DOCUMENTS = "internal_documents"
    DATASET_ANALYSIS = "dataset_analysis"


class TaskOrigin(StrEnum):
    PLANNER = "planner"
    CHALLENGER = "challenger"
    HUMAN = "human"


class TaskStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    SKIPPED_BUDGET = "skipped_budget"
    BLOCKED_UNAVAILABLE = "blocked_unavailable"  # the evidence needed does not exist in reach


class AnalysisRequest(DomainModel):
    """A request for a deterministic analytical operation (see ``sip.tools.analytics``)."""

    operation: str
    dataset_id: str
    params: dict[str, Any] = Field(default_factory=dict)


class ResearchTask(DomainModel):
    id: str = Field(default_factory=lambda: new_id("tsk"))
    question: str
    hypothesis_ids: list[str] = Field(default_factory=list)
    required_evidence: str = ""
    method: ResearchMethod
    preferred_source_types: list[SourceType] = Field(default_factory=list)
    queries: list[str] = Field(default_factory=list)
    analysis: AnalysisRequest | None = None
    required_dataset_role: str | None = None  # set when the task needs data we may not hold
    origin: TaskOrigin = TaskOrigin.PLANNER
    priority: Level = Level.MEDIUM
    expected_value: Level = Level.MEDIUM
    expected_value_rationale: str = ""
    completion_criteria: str = ""
    status: TaskStatus = TaskStatus.PENDING
    status_reason: str = ""
    result_summary: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    iteration: int = 0
    challenge_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None

    @property
    def external(self) -> bool:
        return self.method == ResearchMethod.WEB_SEARCH


class ResearchBudget(DomainModel):
    max_iterations: int = 4
    max_tasks: int = 48
    max_searches: int = 40
    max_fetches: int = 80
    max_llm_calls: int = 250
    max_cost_usd: float = 5.0


class Usage(DomainModel):
    """Accumulated resource usage. Summed by a LangGraph reducer across parallel branches."""

    searches: int = 0
    fetches: int = 0
    analyses: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            searches=self.searches + other.searches,
            fetches=self.fetches + other.fetches,
            analyses=self.analyses + other.analyses,
            llm_calls=self.llm_calls + other.llm_calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cost_usd=round(self.cost_usd + other.cost_usd, 6),
        )

    def exhausted(self, budget: ResearchBudget) -> list[str]:
        reasons = []
        if self.searches >= budget.max_searches:
            reasons.append("search budget exhausted")
        if self.fetches >= budget.max_fetches:
            reasons.append("fetch budget exhausted")
        if self.llm_calls >= budget.max_llm_calls:
            reasons.append("model-call budget exhausted")
        if self.cost_usd >= budget.max_cost_usd:
            reasons.append("cost budget exhausted")
        return reasons


class StopReason(StrEnum):
    SUFFICIENT = "sufficient_evidence"
    BUDGET = "budget_exhausted"
    MAX_ITERATIONS = "max_iterations_reached"
    NO_NEW_TASKS = "no_further_tasks_of_value"
    DIMINISHING_RETURNS = "diminishing_returns"


class RoutingDecision(DomainModel):
    """Why the graph looped or stopped after a challenge round. Persisted for audit and UI."""

    iteration: int
    continue_research: bool
    stop_reason: StopReason | None = None
    rationale: str
    open_blocking_challenges: int = 0
    new_evidence_last_round: int = 0
    at: datetime = Field(default_factory=utcnow)
