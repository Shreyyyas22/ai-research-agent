import asyncio
import logging
import time
from typing import Any

from app.observability.logging import log_event
from app.schemas.research import ResearchTask
from app.tools.base import Tool
from app.tools.tracker import get_active_tool_call_tracker


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
        self._lock: asyncio.Lock | None = None
        self._tool_call_count = 0

    def reset_tool_call_count(self) -> None:
        """Reset the instance-level tool call count."""
        self._tool_call_count = 0

    async def _try_reserve_tool_call(self) -> bool:
        tracker = get_active_tool_call_tracker()
        if tracker is not None:
            return await tracker.try_reserve()

        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._tool_call_count < self.max_tool_calls:
                self._tool_call_count += 1
                try:
                    from app.observability.metrics import record_tool_call

                    record_tool_call(1)
                except Exception:
                    pass
                return True
            log_event(
                "limit_violation",
                level=logging.WARNING,
                logger_name="app.agents.researcher",
                limit="max_tool_calls",
                max_tool_calls=self.max_tool_calls,
                tool_calls=self._tool_call_count,
            )
            try:
                from app.observability.metrics import record_limit_violation

                record_limit_violation("max_tool_calls")
            except Exception:
                pass
            return False

    async def execute_task(
        self,
        task: ResearchTask,
    ) -> list[dict[str, Any]]:
        web_search = self.tools.get("web_search")

        if web_search is None:
            raise ValueError(
                "web_search tool is not registered."
            )

        queries = task.search_queries

        async def run_query(query: str) -> dict[str, Any] | None:
            if not await self._try_reserve_tool_call():
                return None

            async with self.tool_semaphore:
                started_at = time.perf_counter()
                log_event(
                    "tool_call_started",
                    logger_name="app.agents.researcher",
                    tool="web_search",
                )
                try:
                    result = await asyncio.wait_for(
                        web_search.execute({"query": query}),
                        timeout=self.max_execution_time,
                    )
                except asyncio.TimeoutError:
                    log_event(
                        "tool_call_timeout",
                        level=logging.WARNING,
                        logger_name="app.agents.researcher",
                        tool="web_search",
                        timeout_seconds=self.max_execution_time,
                    )
                    return {
                        "success": False,
                        "results": [],
                        "error": "Execution timed out.",
                    }

                except Exception as exc:
                    log_event(
                        "tool_call_failed",
                        level=logging.ERROR,
                        logger_name="app.agents.researcher",
                        tool="web_search",
                        error_type=type(exc).__name__,
                    )
                    return {
                        "success": False,
                        "results": [],
                        "error": str(exc),
                    }

                log_event(
                    "tool_call_completed",
                    logger_name="app.agents.researcher",
                    tool="web_search",
                    success=bool(result.get("success"))
                    if isinstance(result, dict)
                    else None,
                    duration_seconds=round(time.perf_counter() - started_at, 6),
                )
                return result

        results = await asyncio.gather(
            *(run_query(query) for query in queries)
        )

        return [res for res in results if res is not None]

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