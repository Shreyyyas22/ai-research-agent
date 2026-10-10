from __future__ import annotations

import datetime
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
import re
import traceback
from functools import wraps

_LOGGING_RUN_ID: ContextVar[str | None] = ContextVar(
    "logging_run_id", default=None
)
_LOGGING_TRACE_ID: ContextVar[str | None] = ContextVar(
    "logging_trace_id", default=None
)
_LOGGING_NODE_NAME: ContextVar[str | None] = ContextVar(
    "logging_node_name", default=None
)

# (pattern, replacement). Replacements may use regex backreferences.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"gsk_[A-Za-z0-9_-]{10,}"), "[REDACTED_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{10,}"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)\bBearer\s+\S+"), "Bearer [REDACTED]"),
    (
        re.compile(
            r"(?i)(password|secret|api_key|token)=\"?([^\s\"']+)\"?"
        ),
        r"\1=[REDACTED]",
    ),
)

_STANDARD_LOG_ATTRS = set(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}


def redact_secrets(text: str) -> str:
    """Redact known sensitive tokens and secrets from logged strings."""
    if not text:
        return text

    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)

    return text


def get_current_run_id() -> str | None:
    return _LOGGING_RUN_ID.get()


def get_current_trace_id() -> str | None:
    return _LOGGING_TRACE_ID.get()


def get_current_node_name() -> str | None:
    return _LOGGING_NODE_NAME.get()


@contextmanager
def bind_logging_context(
    run_id: str | None = None,
    trace_id: str | None = None,
    node_name: str | None = None,
) -> Iterator[None]:
    """Bind structured execution context to log statements."""
    tokens = []
    if run_id is not None:
        tokens.append((_LOGGING_RUN_ID, _LOGGING_RUN_ID.set(run_id)))
    if trace_id is not None:
        tokens.append((_LOGGING_TRACE_ID, _LOGGING_TRACE_ID.set(trace_id)))
    if node_name is not None:
        tokens.append((_LOGGING_NODE_NAME, _LOGGING_NODE_NAME.set(node_name)))

    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class JSONFormatter(logging.Formatter):
    """Format log records as structured JSON dictionaries."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_secrets(record.getMessage()),
        }

        run_id = getattr(record, "run_id", get_current_run_id())
        trace_id = getattr(record, "trace_id", get_current_trace_id())
        node_name = getattr(record, "node_name", get_current_node_name())

        if run_id is not None:
            log_obj["run_id"] = run_id
        if trace_id is not None:
            log_obj["trace_id"] = trace_id
        if node_name is not None:
            log_obj["node_name"] = node_name

        if record.exc_info:
            exc_type, exc_val, exc_tb = record.exc_info
            log_obj["error"] = {
                "type": exc_type.__name__ if exc_type else "Exception",
                "message": redact_secrets(str(exc_val)),
                "stack_trace": redact_secrets(
                    "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
                ),
            }

        extra_fields = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_ATTRS and not key.startswith("_")
        }
        if extra_fields:
            log_obj["details"] = {
                key: redact_secrets(value) if isinstance(value, str) else value
                for key, value in extra_fields.items()
            }

        return json.dumps(log_obj, default=str)


def configure_logging(
    level: int | str = logging.INFO,
    handler: logging.Handler | None = None,
) -> logging.Logger:
    """Configure the application logger with JSON formatting."""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)

    if not app_logger.handlers:
        log_handler = handler or logging.StreamHandler()
        log_handler.setFormatter(JSONFormatter())
        app_logger.addHandler(log_handler)

    # Keep application records on this logger. The root logger stays unchanged.
    app_logger.propagate = False

    return app_logger


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    logger_name: str = "app",
    exc_info: Any = None,
    **details: Any,
) -> None:
    """Emit one structured event. Details become JSON fields, not the message."""
    logging.getLogger(logger_name).log(
        level,
        event,
        extra=details or None,
        exc_info=exc_info,
    )


def observe_node(
    node_name: str,
    fn: Callable[..., Awaitable[Any]],
) -> Callable[..., Awaitable[Any]]:
    """Log the start, completion, and failure of one graph node."""

    @wraps(fn)
    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        import time

        with bind_logging_context(node_name=node_name):
            log_event(
                "node_started",
                logger_name="app.agents.graph",
            )
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
            except Exception:
                duration = time.perf_counter() - start
                log_event(
                    "node_failed",
                    level=logging.ERROR,
                    logger_name="app.agents.graph",
                    exc_info=True,
                )
                try:
                    from app.observability.metrics import record_node_execution

                    record_node_execution(node_name, duration, succeeded=False)
                except Exception:
                    pass
                raise
            duration = time.perf_counter() - start
            log_event(
                "node_completed",
                logger_name="app.agents.graph",
            )
            try:
                from app.observability.metrics import record_node_execution

                record_node_execution(node_name, duration, succeeded=True)
            except Exception:
                pass
            return result

    return wrapped


logger = logging.getLogger("app")
