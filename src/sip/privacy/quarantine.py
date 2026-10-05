"""Raw content quarantine. Raw uploads are stored here and nowhere else.

Local implementation writes to ``var/quarantine`` with restrictive permissions. The Azure reference
deployment uses a private Blob container reachable only by the gateway's managed identity.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

import httpx


class RawContentStore(Protocol):
    async def put(self, document_id: str, content: bytes) -> None: ...


class LocalQuarantine:
    def __init__(self, root: Path) -> None:
        self.root = root

    async def put(self, document_id: str, content: bytes) -> None:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.root / f"{document_id}.bin"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)


class NullQuarantine:
    """For tests: discards raw content."""

    async def put(self, document_id: str, content: bytes) -> None:
        return None


class BlobQuarantine:
    """Private Azure Blob container, written with the app's managed identity (Storage Blob Data
    Contributor). Uses the Blob REST API directly to avoid an extra SDK dependency."""

    API_VERSION = "2025-01-05"

    def __init__(
        self, container_url: str, token_provider: Callable[[], Awaitable[str]], client: httpx.AsyncClient | None = None
    ) -> None:
        self.container_url = container_url.rstrip("/")
        self.token_provider = token_provider
        self.client = client or httpx.AsyncClient(timeout=30)

    async def put(self, document_id: str, content: bytes) -> None:
        token = await self.token_provider()
        resp = await self.client.put(
            f"{self.container_url}/{document_id}.bin",
            content=content,
            headers={
                "Authorization": f"Bearer {token}",
                "x-ms-version": self.API_VERSION,
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": "application/octet-stream",
            },
        )
        resp.raise_for_status()
