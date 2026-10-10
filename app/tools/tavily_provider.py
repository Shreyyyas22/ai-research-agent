from __future__ import annotations

import os

import httpx

from app.tools.schemas import SearchResponse, SearchResult
from app.tools.search_provider import SearchProvider


class TavilySearchProvider(SearchProvider):
    """Search the web through the Tavily Search API."""

    API_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        max_results: int = 5,
        timeout: float = 15.0,
    ) -> None:
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.max_results = max_results
        self.timeout = timeout

    async def search(self, query: str) -> SearchResponse:
        if not self.api_key:
            return SearchResponse(
                success=False,
                results=[],
                error="TAVILY_API_KEY is not configured",
            )

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": self.max_results,
            "include_answer": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.API_URL, json=payload)
                response.raise_for_status()
                data = response.json()

            results = [
                SearchResult(
                    title=item.get("title") or "Untitled",
                    url=item["url"],
                    snippet=item.get("content") or "",
                )
                for item in data.get("results", [])
                if item.get("url")
            ]

            return SearchResponse(success=True, results=results)

        except (httpx.HTTPError, ValueError, KeyError) as exc:
            return SearchResponse(
                success=False,
                results=[],
                error=f"Tavily search failed: {type(exc).__name__}",
            )
