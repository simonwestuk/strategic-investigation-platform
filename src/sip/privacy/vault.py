"""Pseudonym vault: the reversible mapping between pseudonyms and real values.

This module sits behind a separate security boundary:

* its own database connection (``VAULT_DATABASE_URL``), separate from the application database;
* values are encrypted at rest with a key held outside the database (``SIP_VAULT_KEY``; Key Vault in Azure);
* lookups use a keyed HMAC so equal values map to the same pseudonym without storing plaintext keys;
* nothing under ``sip.graph``, ``sip.agents``, ``sip.research`` or ``sip.tools`` may import it
  (enforced by ``tests/unit/test_architecture_boundaries.py``).

Re-identification is intentionally not exposed through the public API in V1.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Protocol

from cryptography.fernet import Fernet
from sqlalchemy import Column, Integer, MetaData, String, Table, UniqueConstraint, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from sip.privacy.models import EntityType

_DEV_KEY = "sip-local-development-vault-key-not-for-production"


class PseudonymVault(Protocol):
    async def pseudonym_for(self, entity_type: EntityType, value: str) -> str: ...


def _normalise(value: str) -> str:
    return " ".join(value.lower().split())


def _derive(key: str, purpose: bytes) -> bytes:
    return hashlib.sha256(purpose + key.encode()).digest()


class InMemoryVault:
    """Vault for tests and single-process demos."""

    def __init__(self, key: str = _DEV_KEY) -> None:
        self._hmac_key = _derive(key, b"hmac")
        self._map: dict[tuple[str, str], str] = {}
        self._counters: dict[str, int] = {}

    async def pseudonym_for(self, entity_type: EntityType, value: str) -> str:
        digest = hmac.new(self._hmac_key, _normalise(value).encode(), hashlib.sha256).hexdigest()
        key = (entity_type.value, digest)
        if key not in self._map:
            self._counters[entity_type.value] = self._counters.get(entity_type.value, 0) + 1
            self._map[key] = f"{entity_type.value}_{self._counters[entity_type.value]:04d}"
        return self._map[key]

    @property
    def size(self) -> int:
        return len(self._map)


_metadata = MetaData()
pseudonyms = Table(
    "pseudonyms",
    _metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("entity_type", String(32), nullable=False),
    Column("value_hmac", String(64), nullable=False),
    Column("token", String(48), nullable=False, unique=True),
    Column("value_encrypted", String, nullable=False),
    UniqueConstraint("entity_type", "value_hmac", name="uq_entity_value"),
)


class SqlVault:
    """Durable vault on its own database connection, with encrypted values."""

    def __init__(self, engine: AsyncEngine, key: str) -> None:
        self.engine = engine
        self._hmac_key = _derive(key, b"hmac")
        self._fernet = Fernet(base64.urlsafe_b64encode(_derive(key, b"enc")))

    @classmethod
    def from_url(cls, url: str, key: str | None = None, *, production: bool = False) -> SqlVault:
        if production and not key:
            raise RuntimeError("SIP_VAULT_KEY is required in production.")
        return cls(create_async_engine(url), key or _DEV_KEY)

    async def create_schema(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(_metadata.create_all)

    async def pseudonym_for(self, entity_type: EntityType, value: str) -> str:
        digest = hmac.new(self._hmac_key, _normalise(value).encode(), hashlib.sha256).hexdigest()
        async with self.engine.begin() as conn:
            row = (
                await conn.execute(
                    select(pseudonyms.c.token).where(
                        pseudonyms.c.entity_type == entity_type.value, pseudonyms.c.value_hmac == digest
                    )
                )
            ).first()
            if row:
                return str(row[0])
            count = (
                await conn.execute(
                    select(func.count()).select_from(pseudonyms).where(pseudonyms.c.entity_type == entity_type.value)
                )
            ).scalar_one()
            token = f"{entity_type.value}_{count + 1:04d}"
            await conn.execute(
                pseudonyms.insert().values(
                    entity_type=entity_type.value,
                    value_hmac=digest,
                    token=token,
                    value_encrypted=self._fernet.encrypt(value.encode()).decode(),
                )
            )
            return token
