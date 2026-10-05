"""Run a scenario to completion in-process with a scripted human reviewer.

Used by ``sip run`` (terminal demo) and the evaluation harness. The scripted reviewer is explicit about
being a stand-in: its actor id is ``scripted:reviewer`` and every response it gives is recorded in the
audit trail exactly like a real human's. It follows a fixed, documented policy:

* privacy release: approve, except documents containing special-category data, which it rejects
  (the evaluation checks that this choice is respected downstream);
* findings / options: approve;
* decision: commission further investigation, acknowledging every UNKNOWN presented.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from sip.agents.contracts import Reasoner
from sip.config import Settings
from sip.domain import Actor, ActorKind, HumanReview, ResearchBudget, ReviewKind, Role, new_id
from sip.graph.build import RECURSION_LIMIT, build_graph
from sip.graph.checkpoint import open_checkpointer
from sip.graph.context import InMemoryIntake
from sip.privacy.quarantine import NullQuarantine
from sip.privacy.vault import InMemoryVault
from sip.scenarios.loader import Scenario
from sip.services.bootstrap import build_context, ingest_scenario, make_gateway

SCRIPTED_REVIEWER = Actor(
    kind=ActorKind.HUMAN,
    id="scripted:reviewer",
    display_name="Scripted reviewer",
    roles=[Role.PRIVACY_REVIEWER, Role.GOVERNANCE_REVIEWER, Role.DECISION_MAKER, Role.INVESTIGATOR],
)


def scripted_response(review: HumanReview) -> dict[str, Any]:
    actor = SCRIPTED_REVIEWER.model_dump(mode="json")
    if review.kind == ReviewKind.PRIVACY_RELEASE:
        items = []
        for d in review.context.get("documents", []):
            special = bool(d.get("special_category_types"))
            items.append(
                {
                    "item_id": d["id"],
                    "action": "reject" if special else "approve",
                    "note": "Special-category data is not needed for this question." if special else None,
                }
            )
        return {"action": "approve", "actor": actor, "items": items}
    if review.kind == ReviewKind.DECISION:
        unknowns = [u["id"] for u in review.context.get("unknowns_to_acknowledge", [])]
        return {
            "action": "decide",
            "actor": actor,
            "decision": {
                "decision_type": "commission_further_investigation",
                "statement": "Commission research on the unresolved questions before committing to a portfolio change.",
                "rationale": "Scripted evaluation reviewer: material unknowns remain.",
                "option_ids": [],
                "uncertainties_acknowledged": True,
                "acknowledged_unknown_claim_ids": unknowns,
            },
        }
    if review.kind == ReviewKind.CLARIFICATION:
        return {"action": "approve", "actor": actor, "note": "Proceed with the question as framed."}
    return {"action": "approve", "actor": actor}


@dataclass
class RunResult:
    investigation_id: str
    state: dict[str, Any]
    interrupts: list[dict[str, Any]] = field(default_factory=list)
    elapsed_s: float = 0.0


async def run_scenario_to_completion(
    scenario: Scenario,
    settings: Settings,
    *,
    reasoner: Reasoner | None = None,
    budget: ResearchBudget | None = None,
    respond: Callable[[HumanReview], dict[str, Any]] = scripted_response,
    max_interrupts: int = 12,
    on_update: Callable[[str, Any], None] | None = None,
) -> RunResult:
    started = time.perf_counter()
    inv = new_id("inv")
    gateway = make_gateway(settings, InMemoryVault(), NullQuarantine(), scenario)
    intake = await ingest_scenario(scenario, gateway, inv)
    ctx = build_context(settings, scenario, intake.catalog, InMemoryIntake(intake.documents), reasoner=reasoner)
    interrupts: list[dict[str, Any]] = []
    async with open_checkpointer("memory") as cp:
        graph = build_graph(cp)
        cfg: RunnableConfig = {
            "configurable": {"thread_id": inv},
            "recursion_limit": RECURSION_LIMIT,
            "metadata": {"investigation_id": inv, "scenario": scenario.id},
        }
        command: Any = {
            "investigation_id": inv,
            "scenario_id": scenario.id,
            "question": scenario.question,
            "organisation": scenario.organisation,
            "context": scenario.context,
            "as_of": scenario.as_of,
            "budget": budget or ResearchBudget(),
            "iteration": 0,
        }
        for _ in range(max_interrupts):
            async for update in graph.astream(command, cfg, context=ctx, stream_mode="updates"):
                for node, value in update.items():
                    if on_update:
                        on_update(node, value)
            snap = await graph.aget_state(cfg)
            if not snap.next:
                break
            review = snap.values["reviews"][snap.values["pending_review_id"]]
            response = respond(review)
            interrupts.append(
                {
                    "kind": review.kind.value,
                    "review_id": review.id,
                    "action": response["action"],
                    "policy_rule_ids": review.policy_rule_ids,
                }
            )
            command = Command(resume=response)
        snap = await graph.aget_state(cfg)
    return RunResult(
        investigation_id=inv,
        state=dict(snap.values),
        interrupts=interrupts,
        elapsed_s=round(time.perf_counter() - started, 2),
    )
