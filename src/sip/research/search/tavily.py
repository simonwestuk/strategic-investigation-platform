"""Tavily search provider (https://docs.tavily.com/documentation/api-reference/endpoint/search)."""

from __future__ import annotations

from datetime import date

import httpx

from sip.research.search.base import SearchError, SearchResult

ENDPOINT = "https://api.tavily.com/search"


class TavilySearch:
    name = "tavily"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=20)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        body = {"query": query, "max_results": max_results, "search_depth": "basic",
                "include_published_date": True, "include_answer": False}
        try:
            resp = await self._client.post(ENDPOINT, json=body,
                                           headers={"Authorization": f"Bearer {self._key}"})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchError(f"Tavily search failed: {exc.__class__.__name__}") from exc
        out = []
        for r in resp.json().get("results", []):
            published = None
            if r.get("published_date"):
                try:
                    published = date.fromisoformat(r["published_date"][:10])
                except ValueError:
                    published = None
            out.append(SearchResult(url=r["url"], title=r.get("title", ""), snippet=r.get("content", ""),
                                    published_on=published, score=r.get("score"), provider=self.name))
        return out
