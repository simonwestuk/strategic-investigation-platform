"""Offline corpus provider: BM25 search and fetch over a scenario's synthetic web corpus.

Used for CI, credential-free demos and reproducible evaluation. It implements the same interfaces as
live providers, and every source it returns is marked ``synthetic=True`` all the way to the UI.
"""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from sip.domain.sources import SourceType
from sip.research.injection import screen
from sip.research.search.base import FetchedPage, FetchError, SearchResult
from sip.research.text import clean_untrusted
from sip.retrieval.bm25 import BM25Index


def _as_date(v: object) -> date | None:
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return date.fromisoformat(v)
    return None


class OfflineCorpus:
    name = "offline_corpus"

    def __init__(self, corpus_dir: Path) -> None:
        self.pages: dict[str, FetchedPage] = {}
        self.index = BM25Index()
        for path in sorted(corpus_dir.glob("*.md")):
            raw = path.read_text()
            _, front, body = raw.split("---", 2)
            meta = yaml.safe_load(front)
            flags = sorted({f.kind for f in screen(body)})
            text = clean_untrusted(body).strip()
            url = meta["url"]
            page = FetchedPage(
                url=url, title=meta["title"], text=text, content_type="text/markdown",
                sha256=hashlib.sha256(body.encode()).hexdigest(), publisher=meta.get("publisher"),
                domain=urlsplit(url).hostname, published_on=_as_date(meta.get("published_on")),
                updated_on=_as_date(meta.get("updated_on")),
                source_type_hint=SourceType(meta["source_type"]), synthetic=True,
                injection_flags=flags, provider=self.name,
            )
            self.pages[url] = page
            self.index.add(url, f"{page.title} {page.title} {text}")

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        return [
            SearchResult(url=url, title=self.pages[url].title, snippet=self.pages[url].text[:200],
                         published_on=self.pages[url].published_on, score=score, provider=self.name)
            for url, score in self.index.search(query, max_results)
        ]

    async def fetch(self, url: str) -> FetchedPage:
        if url not in self.pages:
            raise FetchError(f"{url} is not in the offline corpus")
        return self.pages[url]
