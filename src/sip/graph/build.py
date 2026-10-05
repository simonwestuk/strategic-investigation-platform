from langgraph.graph import END, START, StateGraph

from sip.graph.state import InvestigationState
from sip.nodes.core import (
    analyse,
    challenge,
    frame_investigation,
    gather_evidence,
    generate_hypotheses,
    governance_gate,
    plan_research,
    synthesise,
)


def after_challenge(state: InvestigationState) -> str:
    return "research" if state["needs_more_research"] else "synthesise"


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("frame", frame_investigation)
    graph.add_node("hypotheses", generate_hypotheses)
    graph.add_node("plan", plan_research)
    graph.add_node("research", gather_evidence)
    graph.add_node("analyse", analyse)
    graph.add_node("challenge", challenge)
    graph.add_node("synthesise", synthesise)
    graph.add_node("governance", governance_gate)

    graph.add_edge(START, "frame")
    graph.add_edge("frame", "hypotheses")
    graph.add_edge("hypotheses", "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "analyse")
    graph.add_edge("analyse", "challenge")
    graph.add_conditional_edges("challenge", after_challenge, {"research": "research", "synthesise": "synthesise"})
    graph.add_edge("synthesise", "governance")
    graph.add_edge("governance", END)
    return graph.compile()
