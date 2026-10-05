"""Investigation graph topology.

    START -> frame -(clarification?)-> intake -(privacy review?)-> hypothesise -> plan
    plan ==Send x N==> research -> evidence_manager -> analyse -> challenge
    challenge -(continue)-> plan          (loop; bounded by budget and max iterations)
    challenge -(stop)-> findings_gate -(blocking challenges open?)-> synthesise -> options_gate
    options_gate -(high consequence?)-> decision_room -> await_review -> END
    await_review routes wherever the human's response sends it (intake/plan/synthesise/... or END).
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sip.graph.context import InvestigationContext
from sip.graph.nodes.analysis import analyse, challenge, evidence_manager, route_after_challenge
from sip.graph.nodes.framing import (
    frame,
    hypothesise,
    intake,
    route_after_frame,
    route_after_intake,
)
from sip.graph.nodes.governance import (
    await_review,
    decision_room,
    findings_gate,
    options_gate,
    route_after_findings,
    route_after_options,
    route_after_review,
    synthesise,
)
from sip.graph.nodes.planning import fan_out, plan
from sip.graph.nodes.research import research
from sip.graph.state import InvestigationState

RECURSION_LIMIT = 250


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    g = StateGraph(InvestigationState, context_schema=InvestigationContext)
    g.add_node("frame", frame, metadata={"agent": "investigation_lead"})
    g.add_node("intake", intake, metadata={"agent": "privacy_release"})
    g.add_node("hypothesise", hypothesise, metadata={"agent": "hypothesis_generator"})
    g.add_node("plan", plan, metadata={"agent": "research_planner"})
    g.add_node("research", research, metadata={"agent": "researcher"})  # type: ignore[arg-type]
    g.add_node("evidence_manager", evidence_manager, metadata={"agent": "evidence_manager"})
    g.add_node("analyse", analyse, metadata={"agent": "analyst"})
    g.add_node("challenge", challenge, metadata={"agent": "sceptic"})
    g.add_node("findings_gate", findings_gate, metadata={"agent": "governance_gate"})
    g.add_node("synthesise", synthesise, metadata={"agent": "strategy_synthesiser"})
    g.add_node("options_gate", options_gate, metadata={"agent": "governance_gate"})
    g.add_node("decision_room", decision_room, metadata={"agent": "decision_room"})
    g.add_node("await_review", await_review, metadata={"agent": "human_review"})

    g.add_edge(START, "frame")
    g.add_conditional_edges("frame", route_after_frame, ["await_review", "intake"])
    g.add_conditional_edges("intake", route_after_intake, ["await_review", "hypothesise", "plan"])
    g.add_edge("hypothesise", "plan")
    g.add_conditional_edges("plan", fan_out, ["research", "analyse"])
    g.add_edge("research", "evidence_manager")
    g.add_edge("evidence_manager", "analyse")
    g.add_edge("analyse", "challenge")
    g.add_conditional_edges("challenge", route_after_challenge, ["plan", "findings_gate"])
    g.add_conditional_edges("findings_gate", route_after_findings, ["await_review", "synthesise"])
    g.add_edge("synthesise", "options_gate")
    g.add_conditional_edges("options_gate", route_after_options, ["await_review", "decision_room"])
    g.add_edge("decision_room", "await_review")
    g.add_conditional_edges("await_review", route_after_review,
                            ["intake", "plan", "synthesise", "options_gate", "decision_room", "await_review", END])
    return g.compile(checkpointer=checkpointer, name="strategic_investigation")
