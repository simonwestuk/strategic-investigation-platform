"""LLM reasoner: each cognitive step is one structured-output call to the model provider.

Instruction/data separation:
* instructions (system rules + task prompt) go in the ``instructions`` channel;
* all variable content goes in ``input``, as JSON for trusted platform data and inside
  ``<untrusted_source>`` blocks for retrieved/uploaded text, with angle brackets escaped so content
  cannot close the block.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any

from pydantic import BaseModel, Field

from sip.agents.contracts import (
    Calls,
    ChallengeDraft,
    ChallengeDrafts,
    ClaimDraft,
    ClaimDrafts,
    EvidenceDraft,
    EvidenceDrafts,
    EvidenceView,
    FindingView,
    FrameDraft,
    HypothesisDraft,
    HypothesisDrafts,
    OptionDraft,
    OptionDrafts,
    PlanningContext,
    SourceTypeDraft,
    SourceView,
    TaskDraft,
)
from sip.agents.taxonomy import Taxonomy, default_taxonomy
from sip.domain.common import Level
from sip.domain.hypotheses import Hypothesis
from sip.domain.investigation import InvestigationFrame
from sip.domain.research import AnalysisRequest, ResearchMethod
from sip.domain.sources import SourceType
from sip.models.base import ModelTier, StructuredModel
from sip.research.text import Passage
from sip.tools.analytics import OPERATION_ROLES

OPERATIONS_CATALOGUE = {
    "trend": "Totals of a dataset's measure per period; params: by (optional dimension).",
    "decompose_change": "Contribution of each value of a dimension to the total change; params: by.",
    "own_vs_market": "Own volume vs market volume per entity, with share; no params.",
    "funnel_conversion": "Stage conversion per entity over time; params: by (optional dimension).",
    "compare_groups": "Did the measure change differently in one group than elsewhere? params: dimension, group, "
    "entity (optional).",
}


@cache
def prompt(name: str) -> str:
    return resources.files("sip.agents").joinpath(f"prompts/{name}.md").read_text()


def instructions(task: str) -> str:
    return prompt("_system") + "\n\n" + prompt(task)


def untrusted(source: SourceView, passages: list[Passage]) -> str:
    def esc(t: str) -> str:
        return t.replace("<", "&lt;").replace(">", "&gt;")

    body = "\n".join(f'<passage index="{p.index}">{esc(p.text)}</passage>' for p in passages)
    return (
        f'<untrusted_source id="{source.id}" type="{source.source_type.value}" '
        f'publisher="{esc(source.publisher or "unknown")}" dated="{source.dated or "undated"}">\n'
        f"{body}\n</untrusted_source>"
    )


def _json(obj: Any) -> str:
    return json.dumps(obj, indent=1, default=str, ensure_ascii=False)


# LLM-facing schema variants: strict structured outputs cannot express free-form dicts.
class AnalysisSpec(BaseModel):
    operation: str
    dataset_id: str
    by: str | None = None
    dimension: str | None = None
    group: str | None = None
    entity: str | None = None


class TaskDraftLLM(BaseModel):
    question: str
    hypothesis_ids: list[str]
    method: ResearchMethod
    queries: list[str]
    analysis: AnalysisSpec | None
    required_dataset_role: str | None
    required_evidence: str
    preferred_source_types: list[SourceType]
    priority: Level
    expected_value: Level
    expected_value_rationale: str
    completion_criteria: str


class TaskDraftsLLM(BaseModel):
    tasks: list[TaskDraftLLM] = Field(max_length=16)


class LLMReasoner:
    name = "llm-structured-v1"

    def __init__(self, model: StructuredModel, taxonomy: Taxonomy | None = None) -> None:
        self.model = model
        self.taxonomy = taxonomy or default_taxonomy()

    async def frame(self, question: str, organisation: str | None, context: str) -> tuple[FrameDraft, Calls]:
        out, call = await self.model.generate(
            task="frame",
            tier=ModelTier.REASONING,
            instructions=instructions("frame"),
            schema=FrameDraft,
            input=_json({"question": question, "organisation": organisation, "context": context}),
        )
        return out, Calls([call])

    async def hypothesise(
        self, frame: InvestigationFrame, datasets: list[dict[str, object]]
    ) -> tuple[list[HypothesisDraft], Calls]:
        taxonomy = {
            k: {"label": c.label, "description": c.statement, "rationale": c.rationale}
            for k, c in self.taxonomy.categories.items()
        }
        out, call = await self.model.generate(
            task="hypothesise",
            tier=ModelTier.REASONING,
            instructions=instructions("hypothesise"),
            schema=HypothesisDrafts,
            input=_json({"frame": frame.model_dump(mode="json"), "driver_taxonomy": taxonomy, "datasets": datasets}),
        )
        return out.hypotheses, Calls([call])

    async def plan(self, ctx: PlanningContext) -> tuple[list[TaskDraft], Calls]:
        payload = {
            "frame": {
                "subject": ctx.frame.subject,
                "organisation": ctx.frame.organisation,
                "objectives": ctx.frame.objectives,
            },
            "hypotheses": [
                {
                    "id": h.id,
                    "statement": h.statement,
                    "category": h.category,
                    "segment": h.segment,
                    "status": h.status.value,
                    "would_support": h.would_support,
                    "would_contradict": h.would_contradict,
                }
                for h in ctx.hypotheses
            ],
            "completed_questions": ctx.completed_task_questions[-40:],
            "open_research_questions": ctx.open_research_questions,
            "datasets": ctx.datasets,
            "operations": {
                k: {"description": v, "requires_roles": [r.value for r in OPERATION_ROLES[k]]}
                for k, v in OPERATIONS_CATALOGUE.items()
            },
            "internal_documents_available": ctx.has_documents,
            "iteration": ctx.iteration,
        }
        out, call = await self.model.generate(
            task="plan",
            tier=ModelTier.REASONING,
            instructions=instructions("plan"),
            schema=TaskDraftsLLM,
            input=_json(payload),
        )
        drafts = []
        for t in out.tasks:
            analysis = None
            if t.analysis is not None:
                params = {
                    k: v
                    for k, v in t.analysis.model_dump().items()
                    if k not in {"operation", "dataset_id"} and v is not None
                }
                analysis = AnalysisRequest(
                    operation=t.analysis.operation, dataset_id=t.analysis.dataset_id, params=params
                )
            drafts.append(TaskDraft(**t.model_dump(exclude={"analysis"}), analysis=analysis))
        return drafts, Calls([call])

    async def extract(
        self, question: str, hypotheses: list[Hypothesis], source: SourceView, passages: list[Passage]
    ) -> tuple[list[EvidenceDraft], Calls]:
        hyps = [{"id": h.id, "statement": h.statement} for h in hypotheses if h.status.value != "split"]
        text = (
            f"Research question: {question}\n\nHypotheses:\n{_json(hyps)}\n\n"
            f"Source metadata (trusted): {_json(source.model_dump(mode='json'))}\n\n{untrusted(source, passages)}"
        )
        out, call = await self.model.generate(
            task="extract",
            tier=ModelTier.EXTRACTION,
            instructions=instructions("extract"),
            schema=EvidenceDrafts,
            input=text,
            metadata={"source_id": source.id},
        )
        return out.evidence, Calls([call])

    async def classify_source(
        self, title: str, domain: str | None, excerpt: str
    ) -> tuple[SourceTypeDraft | None, Calls]:
        view = SourceView(
            id="unclassified",
            title=title,
            publisher=None,
            source_type=SourceType.UNKNOWN,
            dated=None,
            url=None,
            synthetic=False,
        )
        text = (
            f"Domain (trusted): {domain or 'unknown'}\nTitle (untrusted): {title[:200]}\n\n"
            f"{untrusted(view, [Passage(0, excerpt[:1500])])}"
        )
        out, call = await self.model.generate(
            task="classify_source",
            tier=ModelTier.EXTRACTION,
            instructions=instructions("classify_source"),
            schema=SourceTypeDraft,
            input=text,
        )
        return out, Calls([call])

    async def draft_claims(
        self,
        frame: InvestigationFrame,
        hypothesis: Hypothesis,
        evidence: list[EvidenceView],
        blocked_reasons: list[str],
    ) -> tuple[list[ClaimDraft], Calls]:
        payload = {
            "subject": frame.subject,
            "hypothesis": {
                "id": hypothesis.id,
                "statement": hypothesis.statement,
                "category": hypothesis.category,
                "segment": hypothesis.segment,
            },
            "evidence": [e.model_dump(mode="json") for e in evidence],
            "blocked_reasons": blocked_reasons,
        }
        out, call = await self.model.generate(
            task="draft_claims",
            tier=ModelTier.REASONING,
            instructions=instructions("claims"),
            schema=ClaimDrafts,
            input=_json(payload),
            metadata={"hypothesis_id": hypothesis.id},
        )
        return out.claims, Calls([call])

    async def challenge(
        self, frame: InvestigationFrame, claims: list[dict[str, object]], evidence: list[EvidenceView]
    ) -> tuple[list[ChallengeDraft], Calls]:
        if not claims:
            return [], Calls()
        out, call = await self.model.generate(
            task="challenge",
            tier=ModelTier.REASONING,
            instructions=instructions("challenge"),
            schema=ChallengeDrafts,
            input=_json(
                {"subject": frame.subject, "claims": claims, "evidence": [e.model_dump(mode="json") for e in evidence]}
            ),
        )
        return out.challenges, Calls([call])

    async def synthesise(
        self, frame: InvestigationFrame, findings: list[FindingView], unknowns: list[str], caveats: list[str]
    ) -> tuple[list[OptionDraft], Calls]:
        out, call = await self.model.generate(
            task="synthesise",
            tier=ModelTier.REASONING,
            instructions=instructions("synthesise"),
            schema=OptionDrafts,
            input=_json(
                {
                    "frame": {"subject": frame.subject, "decision_context": frame.decision_context},
                    "findings": [f.model_dump(mode="json") for f in findings],
                    "unknowns": unknowns,
                    "caveats": caveats,
                }
            ),
        )
        return out.options, Calls([call])
