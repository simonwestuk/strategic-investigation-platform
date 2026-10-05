"""``sip run``: run a scenario in the terminal and print the investigation's conclusions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sip.config import ReasonerMode, get_settings
from sip.domain import Classification
from sip.scenarios.loader import list_scenarios
from sip.services.scripted import run_scenario_to_completion

_MARK = {"known": "KNOWN     ", "inferred": "INFERRED  ", "hypothesis": "HYPOTHESIS", "unknown": "UNKNOWN   "}


def _progress(node: str, value: Any) -> None:
    if node == "__interrupt__":
        v = value[0].value
        print(f"  ⏸  human review required: {v['title']} (role: {v['required_role']}) — scripted reviewer responds")
    elif node in {"frame", "hypothesise", "plan", "evidence_manager", "analyse", "challenge", "synthesise",
                  "decision_room"}:
        print(f"  → {node}")


async def run_scenario(scenario_id: str, reasoner: str | None, json_out: Path | None) -> None:
    settings = get_settings()
    if reasoner:
        settings = settings.model_copy(update={"sip_reasoner": ReasonerMode(reasoner)})
    scenario = next(s for s in list_scenarios(Path(settings.sip_data_dir)) if s.id == scenario_id)
    print(f"\n{scenario.title}\nQ: {scenario.question}\nReasoner: {settings.sip_reasoner.value} · "
          f"search: {settings.sip_search_provider.value}\n")
    result = await run_scenario_to_completion(scenario, settings, on_update=_progress)
    st = result.state
    claims = [c for c in st.get("claims", {}).values() if c.active]
    print("\nWhat the investigation concluded (causal and unresolved claims):")
    order = [Classification.KNOWN, Classification.INFERRED, Classification.HYPOTHESIS, Classification.UNKNOWN]
    for cls in order:
        for c in claims:
            if c.classification == cls and (c.causal or cls == Classification.UNKNOWN or
                                            c.statement.startswith("Not supported")):
                band = c.confidence.band.value if c.confidence else ""
                print(f"  {_MARK[cls.value]} [{band:9}] {c.statement}")
    print("\nStrategic options (AI recommendations, not decisions):")
    for o in st.get("options", {}).values():
        print(f"  • {o.title}  [consequence {o.consequence.value}, confidence {o.confidence_band.value}]")
    d = st.get("decision")
    print(f"\nHuman decision: {d.decision_type.value} by {d.decided_by.display_name}" if d else "\nNo decision.")
    u = st.get("usage")
    print(f"Usage: {u.searches} searches, {u.fetches} fetches, {u.analyses} analyses, {u.llm_calls} model calls, "
          f"${u.cost_usd:.2f}; {len(st.get('routing', []))} research rounds; {result.elapsed_s}s")
    print(f"Interrupts: {', '.join(i['kind'] for i in result.interrupts)}")
    if json_out:
        json_out.write_text(json.dumps({k: _dump(v) for k, v in st.items()}, indent=1, default=str))
        print(f"State written to {json_out}")


def _dump(v: Any) -> Any:
    if hasattr(v, "model_dump"):
        return v.model_dump(mode="json")
    if isinstance(v, dict):
        return {k: _dump(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dump(x) for x in v]
    return v
