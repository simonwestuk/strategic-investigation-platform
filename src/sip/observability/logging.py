"""Structured logging. JSON in deployed environments (shipped to Application Insights via the
Container Apps log pipeline / OpenTelemetry), console locally. Investigation IDs are bound as context
variables so every log line in a run carries them. Never log document content or detection values."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", json: bool = False) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer(colors=False)
    structlog.configure(processors=[*processors, renderer],
                        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
                        cache_logger_on_first_use=True)
