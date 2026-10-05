"""Wraps a StructuredModel and records every input sent across the model boundary.

Used by evaluation (privacy-leakage grading over what the model actually saw) and by tests.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from sip.models.base import ModelCall, ModelTier, StructuredModel

T = TypeVar("T", bound=BaseModel)


class RecordingModel:
    def __init__(self, inner: StructuredModel) -> None:
        self.inner = inner
        self.inputs: list[str] = []

    async def generate(
        self,
        *,
        task: str,
        tier: ModelTier,
        instructions: str,
        input: str,
        schema: type[T],
        metadata: dict[str, Any] | None = None,
    ) -> tuple[T, ModelCall]:
        self.inputs.append(f"[{task}]\n{instructions}\n{input}")
        return await self.inner.generate(
            task=task, tier=tier, instructions=instructions, input=input, schema=schema, metadata=metadata
        )
