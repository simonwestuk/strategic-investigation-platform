"""Search and fetch interfaces. Core orchestration depends only on these protocols."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from pydantic import BaseModel, Field

from sip.domain.sources import SourceType


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str = ""
    published_on: date | None = None
    score: float | None = None
    provider: str


class FetchedPage(BaseModel):
    url: str  # canonical URL
    title: str
    text: str  # cleaned, untrusted text
    content_type: str
    sha256: str
    publisher: str | None = None
    domain: str | None = None
    published_on: date | None = None
    updated_on: date | None = None
    source_type_hint: SourceType | None = None
    synthetic: bool = False
    injection_flags: list[str] = Field(default_factory=list)
    provider: str


class SearchProvider(Protocol):
    name: str

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]: ...


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> FetchedPage: ...


class FetchError(RuntimeError):
    pass


class SearchError(RuntimeError):
    pass
