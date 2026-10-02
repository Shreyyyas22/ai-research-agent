import asyncio

import pytest

from app.agents.researcher import Researcher
from app.schemas.research import ResearchTask
from app.tools.base import Tool


class TrackingSearchTool(Tool):
    def __init__(self) -> None:
        self.active_calls = 0
        self.max_active_calls = 0

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Fake search tool for concurrency testing."

    async def execute(self, input: dict) -> dict:
        self.active_calls += 1
        self.max_active_calls = max(
            self.max_active_calls,
            self.active_calls,
        )

        await asyncio.sleep(0.05)

        self.active_calls -= 1

        return {
            "success": True,
            "results": [],
            "error": None,
        }


@pytest.mark.asyncio
async def test_researcher_respects_global_concurrency_limit():
    search_tool = TrackingSearchTool()

    researcher = Researcher(
        tools={"web_search": search_tool},
        max_concurrent_queries=3,
        max_tool_calls=5,
        max_research_tasks=3,
    )

    tasks = [
        ResearchTask(
            question="Task 1",
            search_queries=[
                "query 1",
                "query 2",
                "query 3",
            ],
            priority=1,
        ),
        ResearchTask(
            question="Task 2",
            search_queries=[
                "query 4",
                "query 5",
                "query 6",
            ],
            priority=2,
        ),
        ResearchTask(
            question="Task 3",
            search_queries=[
                "query 7",
                "query 8",
                "query 9",
            ],
            priority=3,
        ),
    ]

    results = await researcher.execute_tasks(tasks)

    assert len(results) == 3
    assert search_tool.max_active_calls <= 3