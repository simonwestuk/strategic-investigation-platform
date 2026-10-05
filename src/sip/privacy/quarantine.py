"""Raw content quarantine. Raw uploads are stored here and nowhere else.

Local implementation writes to ``var/quarantine`` with restrictive permissions. The Azure reference
deployment uses a private Blob container reachable only by the gateway's managed identity.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol


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
