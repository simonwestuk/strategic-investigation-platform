"""LangSmith configuration with a privacy-aware content policy.

The privacy boundary already ensures that agents (and therefore traces) only see sanitised content.
``SIP_TRACE_CONTENT`` adds defence in depth:

* ``full``          - trace sanitised inputs/outputs as-is;
* ``redacted``      - additionally scrub anything that still looks like an email, phone number or
                      national ID before it leaves the process (default);
* ``metadata_only`` - send run structure, timings, token usage and metadata but hide inputs/outputs.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from typing import Any

from sip.config import Settings, TraceContentMode

_SCRUB = [
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"(?<![\w+])(?:\+44\s?\(?0?\)?\s?|0)(?:\d\s?){9,10}(?!\w)"), "[PHONE]"),
    (re.compile(r"\b[A-CEGHJ-PR-TW-Z]{2}\s?\d{2}\s?\d{2}\s?\d{2}\s?[A-D]\b"), "[NATIONAL_ID]"),
]


def scrub(value: Any) -> Any:
    if isinstance(value, str):
        for pattern, token in _SCRUB:
            value = pattern.sub(token, value)
        return value
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [scrub(v) for v in value]
    return value


def _hide(_: dict[str, Any]) -> dict[str, Any]:
    return {"hidden": "SIP_TRACE_CONTENT=metadata_only"}


def content_filter(mode: TraceContentMode) -> Callable[[dict[str, Any]], dict[str, Any]] | None:
    if mode == TraceContentMode.METADATA_ONLY:
        return _hide
    if mode == TraceContentMode.REDACTED:
        return scrub
    return None


def configure_tracing(settings: Settings) -> Any | None:
    """Return a configured LangSmith client, or None when tracing is disabled."""
    if not settings.langsmith_tracing or settings.langsmith_api_key is None:
        os.environ["LANGSMITH_TRACING"] = "false"
        return None
    from langsmith import Client

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)
    f = content_filter(settings.sip_trace_content)
    return Client(api_key=settings.langsmith_api_key.get_secret_value(), hide_inputs=f, hide_outputs=f)


def run_metadata(settings: Settings, investigation_id: str, scenario_id: str | None, reasoner: str) -> dict[str, Any]:
    return {
        "investigation_id": investigation_id,
        "scenario": scenario_id or "adhoc",
        "reasoner": reasoner,
        "environment": settings.sip_env.value,
        "model_reasoning": settings.sip_model_reasoning,
        "model_extraction": settings.sip_model_extraction,
    }
