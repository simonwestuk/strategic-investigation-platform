"""Evaluation runner: run each scenario, grade against hidden ground truth, write reports.

    sip eval run [--scenario northstar] [--reasoner offline|llm] [--output DIR] [--langsmith]

Exit code is non-zero if any automated grader falls below its threshold, so CI can gate on it.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evals.graders.ground_truth import GroundTruth, load_ground_truth
from evals.graders.structural import EvalInputs, GraderResult, grade
from sip.agents.contracts import Reasoner
from sip.config import ReasonerMode, Settings, get_settings
from sip.scenarios.loader import Scenario, list_scenarios
from sip.services.scripted import RunResult, run_scenario_to_completion

EVALS_DIR = Path(__file__).parent


def available(settings: Settings) -> list[tuple[Scenario, GroundTruth]]:
    out = []
    for s in list_scenarios(Path(settings.sip_data_dir)):
        gt_path = EVALS_DIR / "scenarios" / s.id / "ground_truth.yaml"
        if gt_path.exists():
            out.append((s, load_ground_truth(gt_path)))
    return out


def _reasoner(settings: Settings) -> tuple[Reasoner | None, Any]:
    if settings.sip_reasoner != ReasonerMode.LLM:
        return None, None
    from sip.agents.llm import LLMReasoner
    from sip.models.azure_openai import AzureOpenAIModel
    from sip.models.recording import RecordingModel

    rec = RecordingModel(AzureOpenAIModel(settings))
    return LLMReasoner(rec), rec


async def evaluate_scenario(
    scenario: Scenario, gt: GroundTruth, settings: Settings
) -> tuple[RunResult, list[GraderResult]]:
    reasoner, recorder = _reasoner(settings)
    result = await run_scenario_to_completion(scenario, settings, reasoner=reasoner)
    inputs = EvalInputs(
        state=result.state, interrupts=result.interrupts, model_inputs=recorder.inputs if recorder else []
    )
    return result, grade(inputs, gt)


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = ["# Evaluation report", ""]
    for r in rows:
        lines += [
            f"## {r['scenario']} — reasoner `{r['reasoner']}`",
            "",
            f"{r['passed']}/{r['automated']} automated graders passed · {r['elapsed_s']}s · "
            f"{r['usage']['searches']} searches · {r['usage']['llm_calls']} model calls · "
            f"${r['usage']['cost_usd']:.2f}",
            "",
            "| Grader | Score | Threshold | Result |",
            "|---|---|---|---|",
        ]
        for g in r["graders"]:
            res = "manual" if g["manual"] else ("pass" if g["passed"] else "**FAIL**")
            lines.append(f"| {g['name']} | {g['score']:.2f} | {g['threshold']:.2f} | {res} |")
        lines += ["", "<details><summary>Details</summary>", ""]
        for g in r["graders"]:
            lines.append(f"**{g['name']}**")
            lines += [f"- {d}" for d in g["details"]]
            lines.append("")
        lines += ["</details>", ""]
    return "\n".join(lines)


async def main(scenarios: list[str] | None, reasoner: str | None, output: Path, langsmith: bool) -> int:
    settings = get_settings()
    if reasoner:
        settings = settings.model_copy(update={"sip_reasoner": ReasonerMode(reasoner)})
    targets = [(s, gt) for s, gt in available(settings) if not scenarios or s.id in scenarios]
    if not targets:
        print("No matching scenarios with ground truth.")
        return 2
    if langsmith:
        from evals.experiments.langsmith_experiment import run_langsmith_experiment

        await run_langsmith_experiment(targets, settings)
    rows = []
    for scenario, gt in targets:
        result, graded = await evaluate_scenario(scenario, gt, settings)
        usage = result.state.get("usage")
        automated = [g for g in graded if not g.manual]
        rows.append(
            {
                "scenario": scenario.id,
                "reasoner": settings.sip_reasoner.value,
                "elapsed_s": result.elapsed_s,
                "interrupts": result.interrupts,
                "usage": usage.model_dump() if usage else {},
                "automated": len(automated),
                "passed": sum(g.passed for g in automated),
                "graders": [g.as_dict() for g in graded],
            }
        )
        print(
            f"\n{scenario.id} ({settings.sip_reasoner.value}): "
            f"{sum(g.passed for g in automated)}/{len(automated)} graders passed"
        )
        for g in graded:
            mark = "  ·" if g.manual else ("  ✓" if g.passed else "  ✗")
            print(f"{mark} {g.name:26} {g.score:.2f} (threshold {g.threshold:.2f})")
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    (output / "report.json").write_text(json.dumps({"generated_at": stamp, "runs": rows}, indent=1, default=str))
    (output / "report.md").write_text(render_markdown(rows))
    print(f"\nReports written to {output}/report.md and report.json")
    return 0 if all(r["passed"] == r["automated"] for r in rows) else 1
