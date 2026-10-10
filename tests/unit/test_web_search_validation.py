import pytest

from app.tools.web_search import WebSearchTool


class UnusedProvider:
    async def search(self, query):
        raise AssertionError("provider should not receive invalid input")


@pytest.mark.asyncio
async def test_web_search_rejects_non_object_input():
    result = await WebSearchTool(UnusedProvider()).execute([])

    assert result == {
        "success": False,
        "results": [],
        "error": "Tool input must be an object.",
    }


@pytest.mark.asyncio
async def test_web_search_rejects_oversized_query():
    result = await WebSearchTool(UnusedProvider()).execute(
        {"query": "x" * 2001}
    )

    assert result["success"] is False
    assert "maximum allowed length" in result["error"]
