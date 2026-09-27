from typing import Any

from app.tools.base import Tool


class FakeSearchTool(Tool):

    @property
    def name(self) -> str:
        return "fake_search"

    @property
    def description(self) -> str:
        return "A fake search tool used for testing."

    async def execute(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:

        query = input["query"]

        return {
            "success": True,
            "results": [
                {
                    "title": "Fake Result",
                    "url": "https://example.com",
                    "snippet": f"Fake result for: {query}",
                }
            ],
            "error": None,
        }