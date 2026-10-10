from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock
from typing import Any, Iterator

from app.observability.logging import log_event


class LLMCallLimitExceeded(RuntimeError):
    """Raised when a research run exceeds its LLM-call limit."""


class UsageTracker:
    """Track LLM request counts, token usage, latency, and estimated cost."""

    def __init__(
        self,
        input_cost_per_million_tokens: float | None = None,
        output_cost_per_million_tokens: float | None = None,
        max_llm_calls: int | None = None,
    ) -> None:
        for name, value in (
            ("input_cost_per_million_tokens", input_cost_per_million_tokens),
            ("output_cost_per_million_tokens", output_cost_per_million_tokens),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")

        if max_llm_calls is not None and (
            isinstance(max_llm_calls, bool)
            or not isinstance(max_llm_calls, int)
            or max_llm_calls < 1
        ):
            raise ValueError("max_llm_calls must be a positive integer.")

        self.max_llm_calls = max_llm_calls
        self._started_calls = 0

        self.input_cost_per_million_tokens = (
            input_cost_per_million_tokens
        )
        self.output_cost_per_million_tokens = (
            output_cost_per_million_tokens
        )

        self._records: list[dict[str, Any]] = []
        self._lock = Lock()

    def reserve_call(self) -> None:
        """Reserve one LLM request slot before making the API call."""
        with self._lock:
            if (
                self.max_llm_calls is not None
                and self._started_calls >= self.max_llm_calls
            ):
                log_event(
                    "limit_violation",
                    level=logging.WARNING,
                    logger_name="app.llm",
                    limit="max_llm_calls",
                    max_llm_calls=self.max_llm_calls,
                )
                try:
                    from app.observability.metrics import record_limit_violation

                    record_limit_violation("max_llm_calls")
                except Exception:
                    pass
                raise LLMCallLimitExceeded(
                    f"Maximum LLM calls per research run "
                    f"({self.max_llm_calls}) exceeded."
                )

            self._started_calls += 1

    def record(
        self,
        *,
        operation: str,
        model: str,
        duration_seconds: float,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        succeeded: bool = True,
    ) -> None:
        """Record one API request, including retries as separate requests."""

        if duration_seconds < 0:
            raise ValueError("duration_seconds cannot be negative.")

        for name, value in (
            ("prompt_tokens", prompt_tokens),
            ("completion_tokens", completion_tokens),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} cannot be negative.")

        cost: float | None = None

        if (
            prompt_tokens is not None
            and completion_tokens is not None
            and self.input_cost_per_million_tokens is not None
            and self.output_cost_per_million_tokens is not None
        ):
            cost = (
                prompt_tokens * self.input_cost_per_million_tokens
                + completion_tokens * self.output_cost_per_million_tokens
            ) / 1_000_000

        record = {
            "operation": operation,
            "model": model,
            "duration_seconds": duration_seconds,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": (
                prompt_tokens + completion_tokens
                if prompt_tokens is not None
                and completion_tokens is not None
                else None
            ),
            "estimated_cost_usd": cost,
            "succeeded": succeeded,
        }

        with self._lock:
            self._records.append(record)

        # Metrics — request counts, latency, errors, token usage
        try:
            from app.observability.metrics import record_llm_request

            record_llm_request(
                duration_seconds,
                operation=operation,
                model=model,
                succeeded=succeeded,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception:
            pass

    def snapshot(self) -> dict[str, Any]:
        """Return a thread-safe aggregate snapshot of recorded usage."""

        with self._lock:
            records = [record.copy() for record in self._records]

        known_prompt_tokens = [
            r["prompt_tokens"]
            for r in records
            if r["prompt_tokens"] is not None
        ]
        known_completion_tokens = [
            r["completion_tokens"]
            for r in records
            if r["completion_tokens"] is not None
        ]

        costs = [r["estimated_cost_usd"] for r in records]
        priced_records = [cost for cost in costs if cost is not None]

        return {
            "llm_calls": len(records),
            "successful_llm_calls": sum(
                record["succeeded"] for record in records
            ),
            "failed_llm_calls": sum(
                not record["succeeded"] for record in records
            ),
            "prompt_tokens": sum(known_prompt_tokens),
            "completion_tokens": sum(known_completion_tokens),
            "total_tokens": (
                sum(known_prompt_tokens) + sum(known_completion_tokens)
            ),
            "token_usage_complete": all(
                record["prompt_tokens"] is not None
                and record["completion_tokens"] is not None
                for record in records
            ),
            "llm_duration_seconds": round(
                sum(record["duration_seconds"] for record in records),
                6,
            ),
            "estimated_cost_usd": (
                round(sum(priced_records), 10)
                if records and len(priced_records) == len(records)
                else None
            ),
            "cost_estimate_complete": (
                bool(records) and len(priced_records) == len(records)
            ),
            "calls": records,
            
        }

_ACTIVE_USAGE_TRACKER: ContextVar[UsageTracker | None] = ContextVar(
    "active_usage_tracker",
    default=None,
)


def get_active_usage_tracker() -> UsageTracker | None:
    """Return the tracker active in the current execution context."""
    return _ACTIVE_USAGE_TRACKER.get()


@contextmanager
def use_usage_tracker(tracker: UsageTracker) -> Iterator[None]:
    """Activate a tracker for one execution context and restore it afterward."""
    token = _ACTIVE_USAGE_TRACKER.set(tracker)

    try:
        yield
    finally:
        _ACTIVE_USAGE_TRACKER.reset(token)
