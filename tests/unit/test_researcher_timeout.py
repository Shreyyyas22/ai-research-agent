import asyncio

import pytest

from app.agents.researcher import Researcher
from app.schemas.research import ResearchTask
from app.tools.base import Tool


class SlowSearchTool(Tool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Fake slow search tool for timeout testing."

    async def execute(self, input: dict) -> dict:
        await asyncio.sleep(0.2)

        return {
            "success": True,
            "results": [],
            "error": None,
        }


@pytest.mark.asyncio
async def test_researcher_respects_execution_time_limit():
    researcher = Researcher(
        tools={"web_search": SlowSearchTool()},
        max_concurrent_queries=3,
        max_tool_calls=3,
        max_execution_time=0.05,
    )

    task = ResearchTask(
        question="Test timeout handling",
        search_queries=[
            "slow query 1",
            "slow query 2",
            "slow query 3",
        ],
        priority=1,
    )

    results = await researcher.execute_task(task)

    assert len(results) == 3
    assert all(result["success"] is False for result in results)
    assert all(result["error"] == "Execution timed out." for result in results)