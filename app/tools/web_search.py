from typing import Any

from app.tools.base import Tool
from app.tools.search_provider import SearchProvider

class WebSearchTool(Tool):
    max_query_length = 2000

    def __init__(self, provider: SearchProvider) -> None:
        self.provider = provider

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for relevant information."

    async def execute(
        self, input: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(input, dict):
            return {
                "success": False,
                "results": [],
                "error": "Tool input must be an object.",
            }

        query = input.get("query")
        if not isinstance(query, str) or not query.strip():
            return {
                "success": False,
                "results": [],
                "error": "Query must be a non-empty string."
            }

        if len(query) > self.max_query_length:
            return {
                "success": False,
                "results": [],
                "error": "Query exceeds the maximum allowed length.",
            }
        
        response = await self.provider.search(query)

        return response.model_dump()
