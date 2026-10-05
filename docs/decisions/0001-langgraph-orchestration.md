# 0001 — LangGraph for orchestration, not a single autonomous agent

**Context.** The investigation must loop (challenger → more research), fan out research in parallel,
pause for humans for hours or days, survive restarts, and be bounded. A single tool-calling agent loop
makes control flow implicit in the model, hard to bound, and hard to audit.

**Decision.** A LangGraph `StateGraph` with typed state, explicit nodes per role, conditional routing
computed by code, `Send` fan-out for research, `interrupt()` for human review, and a Postgres
checkpointer.

**Consequences.** Control flow is inspectable and testable (`tests/integration/test_graph.py`); loops are
bounded by code; HITL is durable. Cost: more structure than a "ReAct" agent, and LangGraph-specific
patterns (e.g. interrupted nodes re-run from the top, so gates and the interrupt node are separate).
Rejected: a "crew" of chatty agents (agreement-biased, opaque) and a fixed chain (cannot loop on evidence).
