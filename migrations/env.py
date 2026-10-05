"""Alembic environment: async engine, URL from application settings."""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from sip.config import get_settings
from sip.persistence.db import make_engine
from sip.persistence.tables import metadata

target_metadata = metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True,
                      render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


async def run_async() -> None:
    url = context.config.attributes.get("database_url") or get_settings().database_url
    engine = make_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(_run)
        await conn.commit()
    await engine.dispose()


if context.is_offline_mode():
    context.configure(url=get_settings().database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_async())
