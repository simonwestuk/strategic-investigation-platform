"""Test double: returns scripted structured outputs and records every prompt it receives.

Recording prompts lets tests assert what crossed the agent/model boundary (privacy leakage, prompt
injection separation) without a live model.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from pydantic import BaseModel

from sip.models.base import ModelCall, ModelError, ModelTier

T = TypeVar("T", bound=BaseModel)


@dataclass
class RecordedCall:
    task: str
    tier: ModelTier
    instructions: str
    input: str


@dataclass
class ScriptedModel:
    responders: dict[str, Callable[[str], BaseModel]] = field(default_factory=dict)
    calls: list[RecordedCall] = field(default_factory=list)

    async def generate(self, *, task: str, tier: ModelTier, instructions: str, input: str,
                       schema: type[T], metadata: dict[str, Any] | None = None) -> tuple[T, ModelCall]:
        self.calls.append(RecordedCall(task, tier, instructions, input))
        if task not in self.responders:
            raise ModelError(f"No scripted response for task '{task}'")
        result = self.responders[task](input)
        if not isinstance(result, schema):
            result = schema.model_validate(result.model_dump())
        return result, ModelCall(task=task, model="scripted", input_tokens=len(input) // 4,
                                 output_tokens=50)
