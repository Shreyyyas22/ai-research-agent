from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

from app.observability.logging import bind_logging_context, get_current_trace_id, log_event

# Re-export context helpers
__all__ = [
    "get_current_trace_id",
    "create_trace_id",
    "create_span",
    "trace_node",
    "trace_llm_request",
    "trace_tool_call",
]

_TRACE_ID: ContextVar[str | None] = ContextVar("tracing_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("tracing_span_id", default=None)


def create_trace_id() -> str:
    return uuid.uuid4().hex


def create_span_id() -> str:
    return uuid.uuid4().hex[:16]


@contextmanager
def create_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Distributed tracing span — logs start/end with trace_id/span_id.

    Uses stdlib logging (no opentelemetry dep). Propagates trace_id via
    logging context and metrics via node_duration.
    """
    from app.observability.metrics import record_node_execution

    tid = trace_id or get_current_trace_id() or create_trace_id()
    span_id = create_span_id()
    start = time.perf_counter()
    # Bind trace context for logs inside span
    with bind_logging_context(trace_id=tid):
        log_event(
            "trace_span_started",
            logger_name="app.observability.tracing",
            span_name=name,
            span_id=span_id,
            trace_id=tid,
            **(attributes or {}),
        )
        try:
            yield {"trace_id": tid, "span_id": span_id, "name": name}
        except Exception:
            duration = time.perf_counter() - start
            log_event(
                "trace_span_failed",
                logger_name="app.observability.tracing",
                span_name=name,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
                exc_info=True,
            )
            # record failure metric for node-like spans
            try:
                record_node_execution(name, duration, succeeded=False)
            except Exception:
                pass
            raise
        else:
            duration = time.perf_counter() - start
            log_event(
                "trace_span_completed",
                logger_name="app.observability.tracing",
                span_name=name,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
            )
            try:
                record_node_execution(name, duration, succeeded=True)
            except Exception:
                pass


def trace_node(node_name: str):
    """Decorator for tracing graph nodes (wraps observe_node semantics)."""
    import functools
    from collections.abc import Awaitable, Callable

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            with create_span(f"node.{node_name}", {"node": node_name}):
                return await fn(*args, **kwargs)

        return wrapped

    return decorator


@contextmanager
def trace_llm_request(operation: str, model: str | None = None) -> Iterator[dict[str, Any]]:
    tid = get_current_trace_id() or create_trace_id()
    span_id = create_span_id()
    start = time.perf_counter()
    with bind_logging_context(trace_id=tid):
        log_event(
            "trace_llm_started",
            logger_name="app.observability.tracing",
            operation=operation,
            model=model,
            span_id=span_id,
            trace_id=tid,
        )
        try:
            yield {"trace_id": tid, "span_id": span_id}
        except Exception:
            duration = time.perf_counter() - start
            log_event(
                "trace_llm_failed",
                logger_name="app.observability.tracing",
                operation=operation,
                model=model,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
                exc_info=True,
            )
            raise
        else:
            duration = time.perf_counter() - start
            log_event(
                "trace_llm_completed",
                logger_name="app.observability.tracing",
                operation=operation,
                model=model,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
            )


@contextmanager
def trace_tool_call(tool_name: str, **attrs: Any) -> Iterator[dict[str, Any]]:
    tid = get_current_trace_id() or create_trace_id()
    span_id = create_span_id()
    start = time.perf_counter()
    with bind_logging_context(trace_id=tid):
        log_event(
            "trace_tool_started",
            logger_name="app.observability.tracing",
            tool=tool_name,
            span_id=span_id,
            trace_id=tid,
            **attrs,
        )
        try:
            yield {"trace_id": tid, "span_id": span_id}
        except Exception:
            duration = time.perf_counter() - start
            log_event(
                "trace_tool_failed",
                logger_name="app.observability.tracing",
                tool=tool_name,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
                exc_info=True,
            )
            raise
        else:
            duration = time.perf_counter() - start
            log_event(
                "trace_tool_completed",
                logger_name="app.observability.tracing",
                tool=tool_name,
                span_id=span_id,
                trace_id=tid,
                duration_seconds=round(duration, 6),
            )
