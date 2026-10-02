import pytest

from app.agents.researcher import Researcher
from app.schemas.research import ResearchTask
from app.tools.base import Tool


class FailingSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Fake search tool for failure testing."

    async def execute(self, input: dict) -> dict:
        query = input["query"]

        if "failure" in query.lower():
            raise RuntimeError("Simulated search failure.")

        return {
            "success": True,
            "results": [
                {
                    "title": f"Result for {query}",
                    "url": "https://example.com",
                    "snippet": "Fake result",
                }
            ],
            "error": None,
        }


@pytest.mark.asyncio
async def test_researcher_isolates_query_failure():
    researcher = Researcher(
        tools={"web_search": FailingSearchTool()},
        max_concurrent_queries=3,
    )

    task = ResearchTask(
        question="Test failure handling",
        search_queries=[
            "successful query",
            "query with failure",
            "another successful query",
        ],
        priority=1,
    )

    results = await researcher.execute_task(task)

    assert len(results) == 3

    assert results[0]["success"] is True
    assert results[1]["success"] is False
    assert "Simulated search failure" in results[1]["error"]
    assert results[2]["success"] is True