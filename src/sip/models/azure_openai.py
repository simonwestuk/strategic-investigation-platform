"""Azure OpenAI / Microsoft Foundry provider using the OpenAI-compatible v1 endpoint.

* Auth: Entra ID (``DefaultAzureCredential`` -> managed identity in Azure, developer login locally) or
  an API key for local development.
* Structured outputs via ``responses.parse`` (default) or ``chat.completions.parse``.
* ``store=False``: prompts and outputs are not retained by the Responses API.
* LangSmith: the client is wrapped with ``langsmith.wrappers.wrap_openai`` when tracing is enabled, so
  model calls appear as child runs of the LangGraph node that issued them, with token usage.
"""

from __future__ import annotations

import time
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from sip.config import LLMApi, LLMAuth, Settings
from sip.models.base import ModelCall, ModelError, ModelTier, cost, parse_prices

T = TypeVar("T", bound=BaseModel)
COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def build_client(settings: Settings) -> AsyncOpenAI:
    if not settings.azure_openai_base_url:
        raise ModelError("AZURE_OPENAI_BASE_URL is required when SIP_REASONER=llm")
    api_key: Any
    if settings.azure_openai_auth == LLMAuth.API_KEY:
        if settings.azure_openai_api_key is None:
            raise ModelError("AZURE_OPENAI_API_KEY is required when AZURE_OPENAI_AUTH=api_key")
        api_key = settings.azure_openai_api_key.get_secret_value()
    else:
        from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider

        api_key = get_bearer_token_provider(DefaultAzureCredential(), COGNITIVE_SERVICES_SCOPE)
    client = AsyncOpenAI(base_url=settings.azure_openai_base_url, api_key=api_key,
                         timeout=settings.sip_llm_timeout_s, max_retries=settings.sip_llm_max_retries)
    if settings.langsmith_tracing:
        from langsmith.wrappers import wrap_openai

        client = wrap_openai(client)
    return client


class AzureOpenAIModel:
    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        self.client = client or build_client(settings)
        self.prices = parse_prices(settings.sip_model_prices)
        self.deployments = {ModelTier.REASONING: settings.sip_model_reasoning,
                            ModelTier.EXTRACTION: settings.sip_model_extraction}

    async def generate(self, *, task: str, tier: ModelTier, instructions: str, input: str,
                       schema: type[T], metadata: dict[str, Any] | None = None) -> tuple[T, ModelCall]:
        model = self.deployments[tier]
        started = time.perf_counter()
        extra: dict[str, Any] = {}
        if self.settings.sip_llm_temperature is not None:
            extra["temperature"] = self.settings.sip_llm_temperature
        if self.settings.sip_llm_api == LLMApi.RESPONSES:
            if self.settings.sip_llm_reasoning_effort:
                extra["reasoning"] = {"effort": self.settings.sip_llm_reasoning_effort}
            resp = await self.client.responses.parse(
                model=model, instructions=instructions, input=input, text_format=schema,
                store=False, **extra)
            parsed = resp.output_parsed
            usage = resp.usage
            inp, out = (usage.input_tokens, usage.output_tokens) if usage else (0, 0)
        else:
            if self.settings.sip_llm_reasoning_effort:
                extra["reasoning_effort"] = self.settings.sip_llm_reasoning_effort
            chat = await self.client.chat.completions.parse(
                model=model, response_format=schema,
                messages=[{"role": "system", "content": instructions}, {"role": "user", "content": input}],
                **extra)
            msg = chat.choices[0].message
            if msg.refusal:
                raise ModelError(f"Model refused task {task}")
            parsed = msg.parsed
            inp, out = (chat.usage.prompt_tokens, chat.usage.completion_tokens) if chat.usage else (0, 0)
        if parsed is None:
            raise ModelError(f"No structured output for task {task}")
        call = ModelCall(task=task, model=model, input_tokens=inp, output_tokens=out,
                         cost_usd=cost(self.prices, model, inp, out),
                         latency_ms=int((time.perf_counter() - started) * 1000))
        return parsed, call
