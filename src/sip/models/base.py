"""Structured-output model interface."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelTier(StrEnum):
    """Which configured deployment to use. Lets cheap models do bulk extraction."""

    REASONING = "reasoning"
    EXTRACTION = "extraction"


class ModelCall(BaseModel):
    task: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class ModelError(RuntimeError):
    pass


class StructuredModel(Protocol):
    async def generate(
        self,
        *,
        task: str,
        tier: ModelTier,
        instructions: str,
        input: str,
        schema: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> tuple[T, ModelCall]: ...


def parse_prices(spec: str) -> dict[str, tuple[float, float]]:
    """"model=in:out;model=in:out" (USD per 1M tokens) -> {model: (in, out)}."""
    prices: dict[str, tuple[float, float]] = {}
    for item in filter(None, (s.strip() for s in spec.split(";"))):
        name, _, rates = item.partition("=")
        i, _, o = rates.partition(":")
        prices[name.strip()] = (float(i), float(o))
    return prices


def cost(prices: dict[str, tuple[float, float]], model: str, inp: int, out: int) -> float:
    if model not in prices:
        return 0.0
    pi, po = prices[model]
    return round((inp * pi + out * po) / 1_000_000, 6)
