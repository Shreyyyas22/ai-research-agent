from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from app.observability.logging import log_event


class ToolCallLimitExceeded(RuntimeError):
    """Raised when a research run exceeds its MAX_TOOL_CALLS limit."""


class ToolCallTracker:
    """Track and enforce run-scoped tool call limits."""

    def __init__(self, max_tool_calls: int | None = None) -> None:
        if max_tool_calls is not None and (
            isinstance(max_tool_calls, bool)
            or not isinstance(max_tool_calls, int)
            or max_tool_calls < 1
        ):
            raise ValueError("max_tool_calls must be a positive integer.")

        self.max_tool_calls = max_tool_calls
        self.count = 0
        self._lock: asyncio.Lock | None = None

    async def try_reserve(self) -> bool:
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if (
                self.max_tool_calls is not None
                and self.count >= self.max_tool_calls
            ):
                log_event(
                    "limit_violation",
                    level=logging.WARNING,
                    logger_name="app.tools",
                    limit="max_tool_calls",
                    max_tool_calls=self.max_tool_calls,
                    tool_calls=self.count,
                )
                try:
                    from app.observability.metrics import record_limit_violation

                    record_limit_violation("max_tool_calls")
                except Exception:
                    pass
                return False
            self.count += 1
            try:
                from app.observability.metrics import record_tool_call

                record_tool_call(1)
            except Exception:
                pass
            return True


_ACTIVE_TOOL_CALL_TRACKER: ContextVar[ToolCallTracker | None] = ContextVar(
    "active_tool_call_tracker",
    default=None,
)


def get_active_tool_call_tracker() -> ToolCallTracker | None:
    """Return the tool call tracker active in the current execution context."""
    return _ACTIVE_TOOL_CALL_TRACKER.get()


@contextmanager
def use_tool_call_tracker(tracker: ToolCallTracker) -> Iterator[None]:
    """Activate a tool call tracker for one execution context and restore it afterward."""
    token = _ACTIVE_TOOL_CALL_TRACKER.set(tracker)
    try:
        yield
    finally:
        _ACTIVE_TOOL_CALL_TRACKER.reset(token)
