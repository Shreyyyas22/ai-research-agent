from typing import Any

from app.tools.base import Tool
from app.tools.search_provider import SearchProvider

class WebSearchTool(Tool):
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

        query = input.get("query")
        if not isinstance(query, str) or not query.strip():
            return {
                "success": False,
                "results": [],
                "error": "Query must be a non-empty string."
            }
        
        response = await self.provider.search(query)

        return response.model_dump()