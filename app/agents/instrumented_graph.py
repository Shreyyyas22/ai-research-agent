import asyncio
import logging
import os
import time
import uuid
from typing import Any

from app.llm.usage import UsageTracker, use_usage_tracker
from app.observability.logging import bind_logging_context, log_event
from app.tools.tracker import ToolCallTracker, use_tool_call_tracker


class ResearchRunTimeoutError(TimeoutError):
    """Raised when a research run exceeds its maximum research time limit."""


class InstrumentedResearchGraph:
    """Wrap a compiled research graph with per-run usage metrics and limits."""

    def __init__(
        self,
        graph: Any,
        max_llm_calls: int | None = None,
        max_tool_calls: int | None = None,
        max_research_time: float | None = None,
        max_agent_iterations: int | None = None,
    ) -> None:
        self._graph = graph

        configured_llm_limit = (
            max_llm_calls
            if max_llm_calls is not None
            else int(os.getenv("MAX_LLM_CALLS", "50"))
        )
        if configured_llm_limit < 1:
            raise ValueError("MAX_LLM_CALLS must be at least 1.")
        self.max_llm_calls = configured_llm_limit

        configured_tool_limit = (
            max_tool_calls
            if max_tool_calls is not None
            else (
                int(os.getenv("MAX_TOOL_CALLS"))
                if os.getenv("MAX_TOOL_CALLS")
                else None
            )
        )
        if configured_tool_limit is not None and configured_tool_limit < 1:
            raise ValueError("MAX_TOOL_CALLS must be at least 1.")
        self.max_tool_calls = configured_tool_limit

        configured_time_limit = (
            max_research_time
            if max_research_time is not None
            else (
                float(os.getenv("MAX_RESEARCH_TIME"))
                if os.getenv("MAX_RESEARCH_TIME")
                else None
            )
        )
        if configured_time_limit is not None and configured_time_limit <= 0:
            raise ValueError("MAX_RESEARCH_TIME must be greater than zero.")
        self.max_research_time = configured_time_limit

        configured_agent_limit = (
            max_agent_iterations
            if max_agent_iterations is not None
            else (
                int(os.getenv("MAX_AGENT_ITERATIONS"))
                if os.getenv("MAX_AGENT_ITERATIONS")
                else None
            )
        )
        if configured_agent_limit is not None and configured_agent_limit < 1:
            raise ValueError("MAX_AGENT_ITERATIONS must be at least 1.")
        self.max_agent_iterations = configured_agent_limit

    def __getattr__(self, name: str) -> Any:
        """Preserve access to the underlying compiled graph's attributes."""
        return getattr(self._graph, name)

    async def ainvoke(
        self,
        input: Any,
        config: Any = None,
        **kwargs: Any,
    ) -> Any:
        """Run the graph and attach metrics to its result."""
        run_id, trace_id = resolve_run_context(input, config)
        tracker = UsageTracker(max_llm_calls=self.max_llm_calls)
        tool_tracker = ToolCallTracker(max_tool_calls=self.max_tool_calls)
        started_at = time.perf_counter()

        with bind_logging_context(run_id=run_id, trace_id=trace_id):
            log_event(
                "research_run_started",
                logger_name="app.agents.instrumented_graph",
                max_llm_calls=self.max_llm_calls,
                max_tool_calls=self.max_tool_calls,
                max_research_time=self.max_research_time,
                max_agent_iterations=self.max_agent_iterations,
            )
            try:
                with use_usage_tracker(tracker), use_tool_call_tracker(tool_tracker):
                    if self.max_research_time is not None:
                        try:
                            result = await asyncio.wait_for(
                                self._graph.ainvoke(
                                    input,
                                    config=config,
                                    **kwargs,
                                ),
                                timeout=self.max_research_time,
                            )
                        except asyncio.TimeoutError as exc:
                            elapsed = time.perf_counter() - started_at
                            log_event(
                                "research_run_timeout",
                                level=logging.ERROR,
                                logger_name="app.agents.instrumented_graph",
                                max_research_time=self.max_research_time,
                            )
                            try:
                                from app.observability.metrics import record_research_run

                                record_research_run(elapsed, "timeout")
                            except Exception:
                                pass
                            raise ResearchRunTimeoutError(
                                f"Research run exceeded maximum duration of {self.max_research_time} seconds."
                            ) from exc
                    else:
                        result = await self._graph.ainvoke(
                            input,
                            config=config,
                            **kwargs,
                        )
            except ResearchRunTimeoutError:
                raise
            except Exception:
                elapsed = time.perf_counter() - started_at
                log_event(
                    "research_run_failed",
                    level=logging.ERROR,
                    logger_name="app.agents.instrumented_graph",
                    exc_info=True,
                )
                try:
                    from app.observability.metrics import record_research_run

                    record_research_run(elapsed, "failure")
                except Exception:
                    pass
                raise

            elapsed_seconds = round(
                time.perf_counter() - started_at,
                6,
            )
            usage = tracker.snapshot()

            if isinstance(result, dict):
                result["usage_metadata"] = usage
                result["elapsed_seconds"] = elapsed_seconds

            log_event(
                "research_run_completed",
                logger_name="app.agents.instrumented_graph",
                elapsed_seconds=elapsed_seconds,
                llm_calls=usage["llm_calls"],
                tool_calls=tool_tracker.count,
            )
            try:
                from app.observability.metrics import record_research_run

                record_research_run(elapsed_seconds, "success")
            except Exception:
                pass

        return result


def _coerce_id(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, uuid.UUID):
        return str(value)
    return None


def resolve_run_context(input: Any, config: Any) -> tuple[str, str]:
    """Choose a run id and trace id from the invocation, or create them."""
    run_id: str | None = None
    trace_id: str | None = None

    if isinstance(input, dict):
        for key in ("run_id", "research_id", "job_id"):
            run_id = _coerce_id(input.get(key))
            if run_id is not None:
                break

    if isinstance(config, dict):
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            configurable = {}
        run_id = (
            run_id
            or _coerce_id(config.get("run_id"))
            or _coerce_id(configurable.get("run_id"))
            or _coerce_id(configurable.get("thread_id"))
        )
        trace_id = _coerce_id(config.get("trace_id")) or _coerce_id(
            configurable.get("trace_id")
        )

    return run_id or uuid.uuid4().hex, trace_id or uuid.uuid4().hex


