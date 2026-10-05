"""Checkpointer construction with an explicit deserialisation allowlist.

LangGraph checkpoints persist graph state (our Pydantic domain objects) as msgpack. Deserialising
arbitrary types from storage is a code-execution risk, so we register exactly the classes we own.
"""

from __future__ import annotations

import enum
import importlib
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

_MODULES = [
    "sip.domain.audit",
    "sip.domain.challenges",
    "sip.domain.claims",
    "sip.domain.classification",
    "sip.domain.common",
    "sip.domain.decisions",
    "sip.domain.evidence",
    "sip.domain.hypotheses",
    "sip.domain.investigation",
    "sip.domain.options",
    "sip.domain.research",
    "sip.domain.reviews",
    "sip.domain.sources",
    "sip.graph.state",
    "sip.privacy.models",
]


def allowed_types() -> list[tuple[str, str]]:
    out = []
    for name in _MODULES:
        mod = importlib.import_module(name)
        for cls_name, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ == name and (issubclass(cls, BaseModel) or issubclass(cls, enum.Enum)):
                out.append((name, cls_name))
    return out


def serializer() -> JsonPlusSerializer:
    return JsonPlusSerializer(allowed_msgpack_modules=allowed_types())


@asynccontextmanager
async def open_checkpointer(database_url: str | None) -> AsyncIterator[BaseCheckpointSaver]:
    """Postgres in deployed environments, SQLite for local single-process runs, memory for tests."""
    serde = serializer()
    if not database_url or database_url.startswith("memory"):
        yield InMemorySaver(serde=serde)
        return
    if database_url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn = database_url.replace("postgresql+psycopg://", "postgresql://")
        async with AsyncPostgresSaver.from_conn_string(conn, serde=serde) as saver:
            await saver.setup()
            yield saver
        return
    if database_url.startswith("sqlite"):
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        path = database_url.split("///", 1)[1].replace("sip.db", "checkpoints.db")
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            saver.serde = serde
            yield saver
        return
    raise ValueError(f"Unsupported checkpoint database URL: {database_url.split(':')[0]}")
