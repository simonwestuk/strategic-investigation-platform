"""Brave Web Search provider (https://api-dashboard.search.brave.com/app/documentation)."""

from __future__ import annotations

import httpx

from sip.research.search.base import SearchError, SearchResult

ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


class BraveSearch:
    name = "brave"

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        self._key = api_key
        self._client = client or httpx.AsyncClient(timeout=20)

    async def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            resp = await self._client.get(
                ENDPOINT, params={"q": query, "count": min(max_results, 20)},
                headers={"X-Subscription-Token": self._key, "Accept": "application/json"})
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise SearchError(f"Brave search failed: {exc.__class__.__name__}") from exc
        return [
            SearchResult(url=r["url"], title=r.get("title", ""), snippet=r.get("description", ""),
                         provider=self.name)
            for r in resp.json().get("web", {}).get("results", [])
        ]
