"""Graph routing, bounded research, and human-in-the-loop behaviour (offline reasoner, offline corpus)."""

from __future__ import annotations

from typing import Any

from sip.config import Settings
from sip.domain import (
    Actor,
    AuditAction,
    ClassificationOverride,
    HumanReview,
    HypothesisStatus,
    ResearchBudget,
    ReviewKind,
    ReviewStatus,
    Role,
    StopReason,
)
from sip.scenarios.loader import Scenario
from sip.services.scripted import SCRIPTED_REVIEWER, RunResult, run_scenario_to_completion, scripted_response


async def test_full_run_interrupts_in_order_and_ends_with_human_decision(northstar_run: RunResult) -> None:
    st = northstar_run.state
    assert [i["kind"] for i in northstar_run.interrupts] == ["privacy_release", "options", "decision"]
    assert st["decision"].decided_by.id == SCRIPTED_REVIEWER.id
    assert all(r.status == ReviewStatus.RESOLVED for r in st["reviews"].values())
    assert st["routing"][-1].stop_reason is not None
    assert len(st["routing"]) <= ResearchBudget().max_iterations


async def test_challenger_sends_investigation_back_to_research(northstar_run: RunResult) -> None:
    st = northstar_run.state
    assert st["routing"][0].continue_research is True
    challenger_tasks = [t for t in st["tasks"].values() if t.origin.value == "challenger"]
    assert challenger_tasks and all(t.status.value == "done" for t in challenger_tasks)
    restructure = next(h for h in st["hypotheses"].values() if h.category == "internal_change")
    assert restructure.status == HypothesisStatus.CONTRADICTED


async def test_evidence_changes_the_hypothesis_tree(northstar_run: RunResult) -> None:
    hyps = northstar_run.state["hypotheses"].values()
    assert any(h.status == HypothesisStatus.SPLIT for h in hyps)
    assert any(h.origin.value == "emergent" for h in hyps)


async def test_unavailable_evidence_is_recorded_not_invented(northstar_run: RunResult) -> None:
    blocked = [t for t in northstar_run.state["tasks"].values() if t.status.value == "blocked_unavailable"]
    assert any("customer_destination" in t.status_reason for t in blocked)


async def test_budget_exhaustion_stops_research(northstar: Scenario) -> None:
    r = await run_scenario_to_completion(
        northstar, Settings(_env_file=None), budget=ResearchBudget(max_searches=2, max_iterations=4)
    )
    assert r.state["routing"][-1].stop_reason == StopReason.BUDGET
    assert r.state["usage"].searches <= 2 + 16  # per-round parallel branches may each spend the last search
    assert r.state["decision"] is not None


async def test_max_iterations_bounds_the_loop(northstar: Scenario) -> None:
    r = await run_scenario_to_completion(northstar, Settings(_env_file=None), budget=ResearchBudget(max_iterations=1))
    assert len(r.state["routing"]) == 1 and r.state["routing"][0].stop_reason == StopReason.MAX_ITERATIONS


async def test_non_human_and_wrong_role_responses_are_refused(northstar: Scenario) -> None:
    attempts: list[str] = []

    def respond(review: HumanReview) -> dict[str, Any]:
        if review.kind == ReviewKind.PRIVACY_RELEASE and len(attempts) < 2:
            bad = (
                Actor.agent("rogue_agent")
                if not attempts
                else Actor(kind="human", id="u:viewer", display_name="Viewer", roles=[Role.VIEWER])
            )
            attempts.append(bad.id)
            return {"action": "approve", "actor": bad.model_dump(mode="json")}
        return scripted_response(review)

    r = await run_scenario_to_completion(northstar, Settings(_env_file=None), respond=respond)
    refused = [a for a in r.state["audit"] if a.action == AuditAction.ACTION_REFUSED and a.subject_type == "review"]
    assert len(refused) == 2
    privacy = next(rv for rv in r.state["reviews"].values() if rv.kind == ReviewKind.PRIVACY_RELEASE)
    assert privacy.response.actor.id == SCRIPTED_REVIEWER.id


async def test_human_can_request_more_research_and_override_classification(northstar: Scenario) -> None:
    state_seen: dict[str, int] = {"options": 0}

    def respond(review: HumanReview) -> dict[str, Any]:
        if review.kind == ReviewKind.OPTIONS and state_seen["options"] == 0:
            state_seen["options"] += 1
            return {
                "action": "request_further_investigation",
                "actor": SCRIPTED_REVIEWER.model_dump(mode="json"),
                "research_requests": ["What do competitors charge for comparable programmes?"],
                "additional_iterations": 1,
            }
        return scripted_response(review)

    r = await run_scenario_to_completion(northstar, Settings(_env_file=None), respond=respond)
    kinds = [i["kind"] for i in r.interrupts]
    assert kinds.count("options") == 2
    assert any(t.origin.value == "human" for t in r.state["tasks"].values())
    assert r.state["budget"].max_iterations == ResearchBudget().max_iterations + 1

    claim = next(c for c in r.state["claims"].values() if c.classification.value == "inferred")
    override = ClassificationOverride(
        claim_id=claim.id, classification="hypothesis", reason="Reviewer doubts causality"
    )

    def respond_override(review: HumanReview) -> dict[str, Any]:
        resp = scripted_response(review)
        if review.kind == ReviewKind.OPTIONS:
            resp["classification_overrides"] = [override.model_dump(mode="json")]
        return resp

    r2 = await run_scenario_to_completion(northstar, Settings(_env_file=None), respond=respond_override)
    overridden = [c for c in r2.state["claims"].values() if c.human_override is not None]
    assert overridden and overridden[0].human_override.actor.kind.value == "human"
    assert any(a.action == AuditAction.CLAIM_OVERRIDDEN for a in r2.state["audit"])


async def test_platform_is_domain_agnostic(harbourline: Scenario) -> None:
    r = await run_scenario_to_completion(harbourline, Settings(_env_file=None))
    supported = {
        (h.category, h.segment) for h in r.state["hypotheses"].values() if h.status == HypothesisStatus.SUPPORTED
    }
    assert ("share_loss", "ESP") in supported and ("market_contraction", "FIL") in supported
    assert r.state["decision"] is not None
