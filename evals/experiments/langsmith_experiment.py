"""Log evaluation runs to LangSmith as an experiment over a versioned dataset.

Each scenario becomes a dataset example (inputs: scenario id + question; reference outputs: the
ground-truth summary). The target runs the investigation (traced) and grades it locally against the
hidden ground truth; LangSmith evaluators surface each grader's score so experiments (e.g. offline
reasoner vs. different model deployments or prompt versions) can be compared side by side.
"""

from __future__ import annotations

from typing import Any

from evals.graders.ground_truth import GroundTruth
from evals.graders.structural import EvalInputs, grade
from sip.config import Settings
from sip.scenarios.loader import Scenario
from sip.services.scripted import run_scenario_to_completion

DATASET = "sip-strategic-scenarios"
GRADER_NAMES = [
    "hypothesis_recall",
    "false_causal_attribution",
    "unknown_detection",
    "contradiction_detection",
    "citation_correctness",
    "citation_completeness",
    "grounding_numeric",
    "source_quality",
    "injection_resistance",
    "governance_compliance",
    "privacy_leakage",
    "research_efficiency",
]


def _evaluator(name: str):  # type: ignore[no-untyped-def]
    def evaluate(outputs: dict[str, Any], reference_outputs: dict[str, Any]) -> dict[str, Any]:
        return {"key": name, "score": outputs["scores"].get(name)}

    evaluate.__name__ = name
    return evaluate


async def run_langsmith_experiment(targets: list[tuple[Scenario, GroundTruth]], settings: Settings) -> None:
    from langsmith import Client, aevaluate

    if settings.langsmith_api_key is None:
        raise SystemExit("LANGSMITH_API_KEY is required for --langsmith")
    client = Client(api_key=settings.langsmith_api_key.get_secret_value())
    if not client.has_dataset(dataset_name=DATASET):
        client.create_dataset(
            DATASET, description="Synthetic strategic-investigation scenarios with hidden ground truth."
        )
    existing = {(e.inputs or {}).get("scenario_id") for e in client.list_examples(dataset_name=DATASET)}
    new = [
        {
            "inputs": {"scenario_id": s.id, "question": s.question},
            "outputs": {"description": gt.description, "planted": [f.id for f in gt.planted_factors]},
        }
        for s, gt in targets
        if s.id not in existing
    ]
    if new:
        client.create_examples(dataset_name=DATASET, examples=new)
    by_id = {s.id: (s, gt) for s, gt in targets}

    async def target(inputs: dict[str, Any]) -> dict[str, Any]:
        scenario, gt = by_id[inputs["scenario_id"]]
        result = await run_scenario_to_completion(scenario, settings)
        graded = grade(EvalInputs(state=result.state, interrupts=result.interrupts), gt)
        return {
            "scores": {g.name: g.score for g in graded if not g.manual},
            "interrupts": [i["kind"] for i in result.interrupts],
        }

    await aevaluate(
        target,
        data=DATASET,
        evaluators=[_evaluator(n) for n in GRADER_NAMES],
        client=client,
        experiment_prefix=f"sip-{settings.sip_reasoner.value}",
        metadata={
            "reasoner": settings.sip_reasoner.value,
            "model": settings.sip_model_reasoning,
            "environment": settings.sip_env.value,
        },
    )
