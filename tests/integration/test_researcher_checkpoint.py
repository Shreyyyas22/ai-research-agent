import asyncio
import time

import pytest

from app.agents.researcher import Researcher
from app.schemas.research import ResearchTask
from app.tools.base import Tool


class CheckpointSearchTool(Tool):
    def __init__(self) -> None:
        self.active_calls = 0
        self.max_active_calls = 0
        self.total_calls = 0

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Fake search tool for Phase 11 checkpoint."

    async def execute(self, input: dict) -> dict:
        query = input["query"]

        self.active_calls += 1
        self.total_calls += 1
        self.max_active_calls = max(
            self.max_active_calls,
            self.active_calls,
        )

        try:
            # Simulate a slow tool.
            if "slow" in query.lower():
                await asyncio.sleep(0.2)

            # Simulate a failing tool.
            if "failure" in query.lower():
                raise RuntimeError("Simulated tool failure.")

            await asyncio.sleep(0.02)

            return {
                "success": True,
                "results": [
                    {
                        "title": f"Result for {query}",
                        "url": "https://example.com",
                        "snippet": "Checkpoint result",
                    }
                ],
                "error": None,
            }

        finally:
            self.active_calls -= 1


@pytest.mark.asyncio
async def test_phase_11_three_task_checkpoint():
    search_tool = CheckpointSearchTool()

    researcher = Researcher(
        tools={"web_search": search_tool},
        max_concurrent_queries=3,
        max_tool_calls=3,
        max_execution_time=0.1,
        max_research_tasks=3,
    )

    tasks = [
        ResearchTask(
            question="Research task 1",
            search_queries=[
                "normal query 1",
                "normal query 2",
            ],
            priority=1,
        ),
        ResearchTask(
            question="Research task 2",
            search_queries=[
                "slow query",
                "failure query",
            ],
            priority=2,
        ),
        ResearchTask(
            question="Research task 3",
            search_queries=[
                "normal query 3",
                "normal query 4",
            ],
            priority=3,
        ),
    ]

    start = time.perf_counter()

    results = await researcher.execute_tasks(tasks)

    elapsed = time.perf_counter() - start

    # Three research tasks completed.
    assert len(results) == 3

    # The global concurrency limit was respected.
    assert search_tool.max_active_calls <= 3

    # All six configured searches were attempted.
    assert search_tool.total_calls == 6

    # Slow/failing calls did not crash the whole research run.
    task_2_results = results[1]["results"]

    assert len(task_2_results) == 2
    assert task_2_results[0]["success"] is False
    assert task_2_results[1]["success"] is False

    # The complete run stayed within a reasonable bound.
    assert elapsed < 0.5