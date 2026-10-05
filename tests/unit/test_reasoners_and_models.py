from datetime import date
from types import SimpleNamespace

import httpx
import pytest
import respx

from sip.agents.contracts import PlanningContext
from sip.agents.llm import AnalysisSpec, LLMReasoner, TaskDraftLLM, TaskDraftsLLM
from sip.agents.offline import OfflineReasoner
from sip.config import LLMApi, Settings
from sip.domain import InvestigationFrame, Level, QuestionType, ResearchMethod
from sip.models.azure_openai import AzureOpenAIModel
from sip.models.base import ModelError, ModelTier, cost, parse_prices
from sip.models.fake import ScriptedModel
from sip.privacy.azure_language import AzureLanguageDetector
from sip.privacy.models import EntityType


async def test_offline_framing_extracts_subject_and_types() -> None:
    draft, _ = await OfflineReasoner().frame(
        "Why has customer churn increased at Acme, and what should we do?", "Acme", ""
    )
    assert draft.subject == "customer churn" and set(draft.question_types) == {"diagnostic", "prescriptive"}
    vague, _ = await OfflineReasoner().frame("Thoughts?", None, "")
    assert vague.needs_clarification


def frame() -> InvestigationFrame:
    return InvestigationFrame(
        question="q",
        question_types=[QuestionType.DIAGNOSTIC],
        subject="sales",
        decision_context="d",
        scope="s",
        as_of=date(2026, 1, 1),
    )


async def test_llm_plan_maps_strict_schema_to_analysis_request() -> None:
    task = TaskDraftLLM(
        question="q",
        hypothesis_ids=["h1"],
        method=ResearchMethod.DATASET_ANALYSIS,
        queries=[],
        analysis=AnalysisSpec(operation="compare_groups", dataset_id="d", dimension="region", group="North"),
        required_dataset_role=None,
        required_evidence="",
        preferred_source_types=[],
        priority=Level.HIGH,
        expected_value=Level.HIGH,
        expected_value_rationale="",
        completion_criteria="",
    )
    model = ScriptedModel(responders={"plan": lambda _: TaskDraftsLLM(tasks=[task])})
    ctx = PlanningContext(
        frame=frame(),
        hypotheses=[],
        completed_task_questions=[],
        open_research_questions=[],
        datasets=[],
        has_documents=False,
        iteration=1,
    )
    drafts, calls = await LLMReasoner(model).plan(ctx)
    assert drafts[0].analysis.params == {"dimension": "region", "group": "North"}
    assert len(calls) == 1 and model.calls[0].tier == ModelTier.REASONING


def test_pricing() -> None:
    prices = parse_prices("m1=1.25:10; m2=0.25:2")
    assert cost(prices, "m1", 1_000_000, 100_000) == 2.25 and cost(prices, "unknown", 10, 10) == 0.0


def _settings(**kw) -> Settings:  # type: ignore[no-untyped-def]
    return Settings(
        _env_file=None,
        azure_openai_base_url="https://x.openai.azure.com/openai/v1/",
        azure_openai_auth="api_key",
        azure_openai_api_key="k",
        sip_model_prices="gpt-test=1:2",
        sip_model_reasoning="gpt-test",
        **kw,
    )


async def test_azure_provider_responses_api_usage_and_cost() -> None:
    parsed = frame()
    calls = {}

    async def parse(**kw):  # type: ignore[no-untyped-def]
        calls.update(kw)
        return SimpleNamespace(output_parsed=parsed, usage=SimpleNamespace(input_tokens=1000, output_tokens=500))

    client = SimpleNamespace(responses=SimpleNamespace(parse=parse))
    model = AzureOpenAIModel(_settings(), client=client)  # type: ignore[arg-type]
    out, call = await model.generate(
        task="t", tier=ModelTier.REASONING, instructions="i", input="x", schema=InvestigationFrame
    )
    assert out is parsed and calls["store"] is False and calls["model"] == "gpt-test"
    assert call.input_tokens == 1000 and call.cost_usd == pytest.approx(0.002)


async def test_azure_provider_chat_refusal_raises() -> None:
    msg = SimpleNamespace(refusal="no", parsed=None)

    async def parse(**kw):  # type: ignore[no-untyped-def]
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    model = AzureOpenAIModel(_settings(sip_llm_api=LLMApi.CHAT_COMPLETIONS), client=client)  # type: ignore[arg-type]
    with pytest.raises(ModelError):
        await model.generate(task="t", tier=ModelTier.REASONING, instructions="i", input="x", schema=InvestigationFrame)


@respx.mock
async def test_azure_language_pii_adapter() -> None:
    text = "Call Jane Smith. She had a medical issue."
    respx.post(url__regex=r"https://lang\.example/language/:analyze-text.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": {
                    "documents": [
                        {
                            "id": "1",
                            "entities": [
                                {
                                    "text": "Jane Smith",
                                    "category": "Person",
                                    "offset": 5,
                                    "length": 10,
                                    "confidenceScore": 0.97,
                                }
                            ],
                        }
                    ]
                }
            },
        )
    )
    found = await AzureLanguageDetector("https://lang.example", "key").detect(text)
    types = [(d.entity_type, d.text) for d in found]
    assert (EntityType.PERSON, "Jane Smith") in types
    assert any(t == EntityType.SPECIAL_CATEGORY for t, _ in types)  # local special-category screen still runs
