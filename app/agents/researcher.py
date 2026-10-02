import asyncio
from typing import Any

from app.schemas.research import ResearchTask
from app.tools.base import Tool


class Researcher:
    """Execute research tasks using registered tools."""

    def __init__(
        self,
        tools: dict[str, Tool],
        max_concurrent_queries: int = 3,
        max_tool_calls: int = 10,
        max_execution_time: float = 30.0,
        max_research_tasks: int = 5,
    ) -> None:
        if max_concurrent_queries <= 0:
            raise ValueError(
                "max_concurrent_queries must be greater than zero."
            )

        if max_tool_calls <= 0:
            raise ValueError(
                "max_tool_calls must be greater than zero."
            )

        if max_execution_time <= 0:
            raise ValueError(
                "max_execution_time must be greater than zero."
            )

        if max_research_tasks <= 0:
            raise ValueError(
                "max_research_tasks must be greater than zero."
            )

        self.tools = tools
        self.max_concurrent_queries = max_concurrent_queries
        self.max_tool_calls = max_tool_calls
        self.max_execution_time = max_execution_time
        self.max_research_tasks = max_research_tasks

        # Shared across all tasks.
        self.tool_semaphore = asyncio.Semaphore(
            max_concurrent_queries
        )

    async def execute_task(
        self,
        task: ResearchTask,
    ) -> list[dict[str, Any]]:
        web_search = self.tools.get("web_search")

        if web_search is None:
            raise ValueError(
                "web_search tool is not registered."
            )

        queries = task.search_queries[: self.max_tool_calls]

        async def run_query(query: str) -> dict[str, Any]:
            async with self.tool_semaphore:
                try:
                    return await asyncio.wait_for(
                        web_search.execute({"query": query}),
                        timeout=self.max_execution_time,
                    )

                except asyncio.TimeoutError:
                    return {
                        "success": False,
                        "results": [],
                        "error": "Execution timed out.",
                    }

                except Exception as exc:
                    return {
                        "success": False,
                        "results": [],
                        "error": str(exc),
                    }

        results = await asyncio.gather(
            *(run_query(query) for query in queries)
        )

        return list(results)

    async def execute_tasks(
        self,
        tasks: list[ResearchTask],
    ) -> list[dict[str, Any]]:
        limited_tasks = tasks[: self.max_research_tasks]

        task_results = await asyncio.gather(
            *(self.execute_task(task) for task in limited_tasks)
        )

        return [
            {
                "question": task.question,
                "priority": task.priority,
                "results": results,
            }
            for task, results in zip(
                limited_tasks,
                task_results,
            )
        ]