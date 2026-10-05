"""Investigation service: the only place that runs the graph, resumes it, and projects its state.

API handlers call this service. It owns:
* creating investigations (optionally seeded from a scenario pack via the privacy gateway);
* background execution with a per-investigation lock (one run at a time per thread);
* resuming interrupts with responses whose actor comes from the authenticated principal;
* projecting state to PostgreSQL after every graph step.

Production note: background execution uses in-process asyncio tasks. A multi-replica deployment would
move execution to a worker (e.g. Container Apps job + queue); checkpoints already make runs resumable.
"""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path
from typing import Any

import structlog
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from langsmith.run_helpers import tracing_context

from sip.config import Settings
from sip.domain import (
    Actor,
    AuditAction,
    AuditEvent,
    DataClassification,
    InvestigationStatus,
    ResearchBudget,
    ReviewKind,
    SourceType,
    new_id,
)
from sip.graph.build import RECURSION_LIMIT
from sip.graph.context import InvestigationContext
from sip.observability.tracing import run_metadata
from sip.persistence.repository import Repository, RepositoryIntake
from sip.privacy.gateway import PrivacyGateway
from sip.privacy.models import IntakeDocument, IntakeKind
from sip.scenarios.loader import Scenario, list_scenarios
from sip.services.bootstrap import build_context, ingest_scenario
from sip.tools.datasets import Dataset, DatasetCatalog

log = structlog.get_logger(__name__)


class NotFound(LookupError):
    pass


class Conflict(RuntimeError):
    pass


class InvestigationService:
    def __init__(self, *, settings: Settings, repo: Repository, graph: CompiledStateGraph,
                 gateway_factory: Any, reasoner: Any = None, tracing_client: Any = None) -> None:
        self.settings = settings
        self.repo = repo
        self.graph = graph
        self.gateway_factory = gateway_factory  # (scenario | None) -> PrivacyGateway
        self.reasoner = reasoner
        self.tracing_client = tracing_client
        self._locks: dict[str, asyncio.Lock] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    # ---- scenarios ----------------------------------------------------------------------------
    def scenarios(self) -> list[Scenario]:
        return list_scenarios(Path(self.settings.sip_data_dir))

    def scenario(self, scenario_id: str) -> Scenario:
        for s in self.scenarios():
            if s.id == scenario_id:
                return s
        raise NotFound(f"Scenario {scenario_id} not found")

    # ---- lifecycle ----------------------------------------------------------------------------
    async def create(self, *, actor: Actor, question: str | None, scenario_id: str | None,
                     organisation: str | None = None, context: str = "",
                     budget: ResearchBudget | None = None) -> str:
        scenario = self.scenario(scenario_id) if scenario_id else None
        if scenario is None and not question:
            raise ValueError("A question is required when no scenario is selected.")
        inv_id = new_id("inv")
        q = question or (scenario.question if scenario else "")
        org = organisation or (scenario.organisation if scenario else None)
        ctx_text = context or (scenario.context if scenario else "")
        as_of = scenario.as_of if scenario else date.today()
        budget = budget or ResearchBudget(
            max_iterations=self.settings.sip_budget_max_iterations, max_tasks=self.settings.sip_budget_max_tasks,
            max_searches=self.settings.sip_budget_max_searches, max_fetches=self.settings.sip_budget_max_fetches,
            max_llm_calls=self.settings.sip_budget_max_llm_calls, max_cost_usd=self.settings.sip_budget_max_cost_usd)
        await self.repo.create_investigation(
            id=inv_id, question=q, scenario_id=scenario_id, organisation=org,
            reasoner=self.settings.sip_reasoner.value, as_of=as_of.isoformat(), created_by=actor.id,
            payload={"context": ctx_text, "budget": budget.model_dump(mode="json")})
        if scenario is not None:
            gateway: PrivacyGateway = self.gateway_factory(scenario)
            intake = await ingest_scenario(scenario, gateway, inv_id, uploaded_by=actor.id)
            manifests = {m.id: m for m in scenario.datasets}
            for doc in intake.documents:
                await self.repo.add_intake(doc, manifests.get(doc.dataset_id) if doc.dataset_id else None)
        await self._audit(inv_id, actor, AuditAction.INVESTIGATION_CREATED, f"Created: {q[:160]}")
        return inv_id

    async def upload(self, *, investigation_id: str, actor: Actor, filename: str, content: bytes,
                     title: str | None, source_type: SourceType, declared: DataClassification) -> IntakeDocument:
        inv = await self._require(investigation_id)
        scenario = self.scenario(inv["scenario_id"]) if inv["scenario_id"] else None
        gateway: PrivacyGateway = self.gateway_factory(scenario)
        doc = await gateway.ingest(filename=filename, content=content, title=title, source_type=source_type,
                                   declared=declared, uploaded_by=actor.id, investigation_id=investigation_id,
                                   kind=IntakeKind.DOCUMENT)
        await self.repo.add_intake(doc)
        await self._audit(investigation_id, actor, AuditAction.DOCUMENT_SCANNED,
                          f"Uploaded '{doc.title}' scanned: {doc.scan.classification.label}",
                          subject_type="intake_document", subject_id=doc.id)
        return doc

    async def start(self, investigation_id: str, actor: Actor) -> None:
        inv = await self._require(investigation_id)
        if inv["status"] != InvestigationStatus.DRAFT.value:
            raise Conflict("Investigation has already been started.")
        p = inv["payload"]
        state = {
            "investigation_id": investigation_id, "scenario_id": inv["scenario_id"], "question": inv["question"],
            "organisation": inv["organisation"], "context": p.get("context", ""),
            "as_of": date.fromisoformat(inv["as_of"]), "reasoner": inv["reasoner"],
            "budget": ResearchBudget.model_validate(p["budget"]), "iteration": 0,
        }
        await self._launch(investigation_id, state)

    async def respond(self, investigation_id: str, review_id: str, response: dict[str, Any]) -> None:
        """Resume a pending interrupt. ``response['actor']`` must come from the authenticated principal."""
        inv = await self._require(investigation_id)
        if investigation_id in self._tasks and not self._tasks[investigation_id].done():
            raise Conflict("Investigation is currently running.")
        snap = await self.graph.aget_state(self._config(investigation_id))
        pending = snap.values.get("pending_review_id")
        if not snap.next or pending != review_id:
            raise Conflict("That review is not awaiting a response.")
        del inv
        await self._launch(investigation_id, Command(resume=response))

    async def wait(self, investigation_id: str) -> None:
        task = self._tasks.get(investigation_id)
        if task is not None:
            await task

    # ---- execution ----------------------------------------------------------------------------
    def _config(self, investigation_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": investigation_id}, "recursion_limit": RECURSION_LIMIT}

    async def _context(self, investigation_id: str, scenario_id: str | None) -> InvestigationContext:
        scenario = self.scenario(scenario_id) if scenario_id else None
        datasets = []
        for doc, manifest in await self.repo.intake_for(investigation_id):
            if doc.kind == IntakeKind.DATASET and manifest is not None:
                datasets.append(Dataset.from_csv(manifest, doc.sanitised_text))
        return build_context(self.settings, scenario, DatasetCatalog(datasets), RepositoryIntake(self.repo),
                             reasoner=self.reasoner)

    async def _launch(self, investigation_id: str, graph_input: Any) -> None:
        lock = self._locks.setdefault(investigation_id, asyncio.Lock())
        if lock.locked():
            raise Conflict("Investigation is currently running.")
        await self.repo.set_status(investigation_id, InvestigationStatus.RUNNING.value)
        self._tasks[investigation_id] = asyncio.create_task(self._run(investigation_id, graph_input, lock))

    async def _run(self, investigation_id: str, graph_input: Any, lock: asyncio.Lock) -> None:
        async with lock:
            inv = await self._require(investigation_id)
            structlog.contextvars.bind_contextvars(investigation_id=investigation_id)
            cfg = self._config(investigation_id)
            meta = run_metadata(self.settings, investigation_id, inv["scenario_id"], inv["reasoner"])
            cfg["metadata"] = meta
            cfg["tags"] = ["sip", inv["scenario_id"] or "adhoc"]
            try:
                ctx = await self._context(investigation_id, inv["scenario_id"])
                with tracing_context(client=self.tracing_client, metadata=meta,
                                     enabled=self.tracing_client is not None):
                    async for _ in self.graph.astream(graph_input, cfg, context=ctx, stream_mode="updates"):
                        snap = await self.graph.aget_state(cfg)
                        await self.repo.save_state(investigation_id, snap.values)
                snap = await self.graph.aget_state(cfg)
                await self.repo.save_state(investigation_id, snap.values)
                await self.repo.set_status(investigation_id, self._status(snap))
                log.info("investigation.run_paused_or_finished", status=self._status(snap))
            except Exception as exc:
                log.exception("investigation.run_failed")
                await self.repo.set_status(investigation_id, InvestigationStatus.FAILED.value,
                                           error=f"{exc.__class__.__name__}: {str(exc)[:500]}")
            finally:
                structlog.contextvars.unbind_contextvars("investigation_id")

    @staticmethod
    def _status(snap: Any) -> str:
        values = snap.values
        if snap.next:
            pending = (values.get("reviews") or {}).get(values.get("pending_review_id") or "")
            if pending is not None and pending.kind == ReviewKind.DECISION:
                return InvestigationStatus.AWAITING_DECISION.value
            return InvestigationStatus.AWAITING_REVIEW.value
        if values.get("decision") is not None:
            return InvestigationStatus.DECIDED.value
        return InvestigationStatus.CLOSED.value

    # ---- helpers ------------------------------------------------------------------------------
    async def _require(self, investigation_id: str) -> dict[str, Any]:
        inv = await self.repo.get_investigation(investigation_id)
        if inv is None:
            raise NotFound(f"Investigation {investigation_id} not found")
        return inv

    async def _audit(self, investigation_id: str, actor: Actor, action: AuditAction, summary: str,
                     **kw: Any) -> None:
        await self.repo.save_state(investigation_id, {"audit": [AuditEvent(actor=actor, action=action,
                                                                          summary=summary, **kw)]})
