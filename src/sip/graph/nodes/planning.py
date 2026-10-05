"""Research Planner node and the fan-out router.

The planner turns hypotheses, challenger questions and human requests into research tasks, then
applies deterministic controls the model cannot override: validation, duplicate detection, detection
of evidence that is not available, and the research budget.
"""

from __future__ import annotations

import json
from typing import Any

from langgraph.runtime import Runtime
from langgraph.types import Send

from sip.agents.contracts import PlanningContext, TaskDraft
from sip.domain import (
    Actor,
    AuditAction,
    ChallengeStatus,
    HypothesisStatus,
    Level,
    ResearchMethod,
    ResearchTask,
    Severity,
    SourceOrigin,
    TaskOrigin,
    TaskStatus,
    utcnow,
)
from sip.graph.context import InvestigationContext
from sip.graph.helpers import audit, policy_event, usage_from
from sip.graph.state import InvestigationState
from sip.research.text import normalise
from sip.tools.analytics import OPERATIONS
from sip.tools.datasets import DatasetRole

PLANNER = Actor.agent("research_planner")
MAX_TASKS_PER_ROUND = 16


def signature(method: ResearchMethod, analysis: Any, queries: list[str], question: str) -> str:
    if analysis is not None:
        return f"{method}:{analysis.operation}:{json.dumps(analysis.params, sort_keys=True)}"
    basis = sorted(normalise(q) for q in queries) or [normalise(question)]
    return f"{method}:{'|'.join(basis)}"


async def plan(state: InvestigationState, runtime: Runtime[InvestigationContext]) -> dict[str, Any]:
    ctx = runtime.context
    fr = state["frame"]
    assert fr is not None
    iteration = state.get("iteration", 0) + 1
    budget = state["budget"]
    tasks = state.get("tasks") or {}
    hyps = state.get("hypotheses") or {}
    challenges = state.get("challenges") or {}
    released = state.get("released_dataset_ids") or {}
    sources = state.get("sources") or {}
    decision = ctx.governance.evaluate("plan_research")

    actionable = [
        c
        for c in challenges.values()
        if c.status == ChallengeStatus.OPEN
        and c.severity in {Severity.BLOCKING, Severity.MAJOR}
        and not c.research_attempted
    ]
    questions = [c.research_question for c in actionable if c.research_question and not c.suggested_analysis]
    human_requests = list(state.get("research_requests") or [])
    pctx = PlanningContext(
        frame=fr,
        hypotheses=list(hyps.values()),
        completed_task_questions=[t.question for t in tasks.values() if t.status == TaskStatus.DONE],
        open_research_questions=questions + human_requests,
        datasets=[d for d in ctx.catalog.describe() if d["id"] in released],
        has_documents=any(
            sources[s].origin == SourceOrigin.INTERNAL for s in state.get("documents") or {} if s in sources
        ),
        iteration=iteration,
    )
    drafts, calls = await ctx.reasoner.plan(pctx)
    origins: list[TaskOrigin] = [TaskOrigin.PLANNER] * len(drafts)
    challenge_for: list[str | None] = [None] * len(drafts)
    for c in actionable:
        if c.suggested_analysis:
            drafts.append(
                TaskDraft(
                    question=f"Disconfirming test for challenge: {c.argument[:160]}",
                    hypothesis_ids=[c.target_id]
                    if c.target_id in hyps
                    else [h for h in (_claim_hyps(state, c.target_id))],
                    method=ResearchMethod.DATASET_ANALYSIS,
                    analysis=c.suggested_analysis,
                    required_evidence="Difference-in-change between groups.",
                    priority=Level.HIGH,
                    expected_value=Level.HIGH,
                    expected_value_rationale="Directly tests a causal claim the challenger disputes.",
                    completion_criteria="Test run and result recorded.",
                )
            )
            origins.append(TaskOrigin.CHALLENGER)
            challenge_for.append(c.id)
    human_q = {normalise(q) for q in human_requests}
    for i, d in enumerate(drafts):
        if origins[i] == TaskOrigin.PLANNER and normalise(d.question) in human_q:
            origins[i] = TaskOrigin.HUMAN

    existing = {signature(t.method, t.analysis, t.queries, t.question): t for t in tasks.values()}
    new: dict[str, ResearchTask] = {}
    merged: dict[str, ResearchTask] = {}
    events = [policy_event(PLANNER, decision)]
    duplicates = 0
    for d, origin, chl in zip(drafts, origins, challenge_for, strict=True):
        hyp_ids = [h for h in d.hypothesis_ids if h in hyps]
        sig = signature(d.method, d.analysis, d.queries, d.question)
        if sig in existing:
            prior = existing[sig]
            if prior.id in new and set(hyp_ids) - set(prior.hypothesis_ids):
                new[prior.id] = prior.model_copy(
                    update={"hypothesis_ids": sorted(set(prior.hypothesis_ids) | set(hyp_ids))}
                )
                existing[sig] = new[prior.id]
            elif prior.id not in new and set(hyp_ids) - set(prior.hypothesis_ids):
                merged[prior.id] = prior.model_copy(
                    update={"hypothesis_ids": sorted(set(prior.hypothesis_ids) | set(hyp_ids))}
                )
            duplicates += 1
            continue
        task = ResearchTask(
            question=d.question,
            hypothesis_ids=hyp_ids,
            method=d.method,
            queries=d.queries[:3],
            analysis=d.analysis,
            required_dataset_role=d.required_dataset_role,
            required_evidence=d.required_evidence,
            preferred_source_types=d.preferred_source_types,
            origin=origin,
            priority=d.priority,
            expected_value=d.expected_value,
            expected_value_rationale=d.expected_value_rationale,
            completion_criteria=d.completion_criteria,
            iteration=iteration,
            challenge_id=chl,
        )
        try:
            task = _validate(task, ctx, released)
        except Exception as exc:  # one malformed proposal must not stop the investigation
            task = task.model_copy(update={"status": TaskStatus.FAILED, "status_reason": f"Invalid task: {exc}"[:300]})
        new[task.id] = task
        existing[sig] = task

    # budget: total task cap and per-round cap, highest priority x value first
    pending = sorted(
        (t for t in new.values() if t.status == TaskStatus.PENDING),
        key=lambda t: -(t.priority.rank * t.expected_value.rank),
    )
    room = max(0, min(MAX_TASKS_PER_ROUND, budget.max_tasks - len(tasks)))
    for t in pending[room:]:
        new[t.id] = t.model_copy(
            update={"status": TaskStatus.SKIPPED_BUDGET, "status_reason": "Research budget or per-round cap reached."}
        )
    for t in new.values():
        action = AuditAction.TASK_CREATED if t.status == TaskStatus.PENDING else AuditAction.TASK_SKIPPED
        events.append(
            audit(
                PLANNER,
                action,
                f"[{t.method.value}] {t.question[:160]}",
                subject_type="task",
                subject_id=t.id,
                status=t.status.value,
                origin=t.origin.value,
            )
        )
    if duplicates:
        events.append(
            audit(PLANNER, AuditAction.TASK_SKIPPED, f"{duplicates} duplicate task proposal(s) merged or skipped.")
        )

    planned_hyps = {h for t in new.values() for h in t.hypothesis_ids}
    hyp_updates = {
        h: hyps[h].model_copy(update={"status": HypothesisStatus.INVESTIGATING, "updated_at": utcnow()})
        for h in planned_hyps
        if hyps[h].status == HypothesisStatus.PROPOSED
    }
    for h in hyps.values():  # nothing could be planned for it: still mark as under investigation
        if h.status == HypothesisStatus.PROPOSED and h.id not in hyp_updates:
            hyp_updates[h.id] = h.model_copy(update={"status": HypothesisStatus.INVESTIGATING})
    chl_updates = {c.id: c.model_copy(update={"research_attempted": True}) for c in actionable}
    return {
        "tasks": {**merged, **new},
        "iteration": iteration,
        "round_task_ids": [t.id for t in new.values() if t.status == TaskStatus.PENDING],
        "hypotheses": hyp_updates,
        "challenges": chl_updates,
        "research_requests": [],
        "audit": events,
        "usage": usage_from(calls),
    }


def _claim_hyps(state: InvestigationState, claim_id: str) -> list[str]:
    claim = (state.get("claims") or {}).get(claim_id)
    return list(claim.related_hypothesis_ids) if claim else []


def _validate(task: ResearchTask, ctx: InvestigationContext, released: dict[str, str]) -> ResearchTask:
    if task.required_dataset_role and not ctx.catalog.has_role(task.required_dataset_role):
        return task.model_copy(
            update={
                "status": TaskStatus.BLOCKED_UNAVAILABLE,
                "completed_at": utcnow(),
                "status_reason": f"No dataset with role '{task.required_dataset_role}' is available. "
                f"Evidence of this kind (e.g. a {task.required_dataset_role.replace('_', ' ')} "
                "extract or survey) would be needed to resolve the question.",
            }
        )
    if task.method == ResearchMethod.DATASET_ANALYSIS:
        a = task.analysis
        if a is None or a.operation not in OPERATIONS:
            return task.model_copy(
                update={"status": TaskStatus.FAILED, "status_reason": "Invalid or missing analysis operation."}
            )
        try:
            ds = ctx.catalog.get(a.dataset_id)
        except KeyError:
            return task.model_copy(
                update={"status": TaskStatus.FAILED, "status_reason": f"Unknown dataset '{a.dataset_id}'."}
            )
        roles_needed = {DatasetRole.MARKET_VOLUME} if a.operation == "own_vs_market" else set()
        if ds.manifest.id not in released or any(
            (d := ctx.catalog.by_role(r)) is None or d.manifest.id not in released for r in roles_needed
        ):
            return task.model_copy(
                update={
                    "status": TaskStatus.BLOCKED_UNAVAILABLE,
                    "status_reason": "Dataset not released through the privacy gateway.",
                }
            )
    return task


def fan_out(state: InvestigationState) -> list[Send] | str:
    ids = state.get("round_task_ids") or []
    if not ids:
        return "analyse"
    tasks = state["tasks"]
    hyps = list(state["hypotheses"].values())
    sources = state.get("sources") or {}
    internal_docs = {
        sid: txt
        for sid, txt in (state.get("documents") or {}).items()
        if sid in sources and sources[sid].origin == SourceOrigin.INTERNAL
    }
    payload_base = {
        "investigation_id": state["investigation_id"],
        "as_of": state["as_of"],
        "hypotheses": hyps,
        "known_urls": sorted({s.canonical_url for s in sources.values() if s.canonical_url}),
        "internal_documents": internal_docs,
        "internal_sources": {k: sources[k] for k in internal_docs},
        "released_dataset_ids": state.get("released_dataset_ids") or {},
        "budget": state["budget"],
        "usage": state.get("usage"),
    }
    return [Send("research", {**payload_base, "task": tasks[i]}) for i in ids]
