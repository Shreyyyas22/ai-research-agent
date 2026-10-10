import asyncio
import logging
import os
import re
import time
from typing import Any, cast

import groq
from dotenv import load_dotenv
from groq import AsyncGroq
from pydantic import BaseModel, ValidationError

from app.llm.usage import (
    UsageTracker,
    get_active_usage_tracker,
)
from app.observability.logging import log_event


load_dotenv()


class ContextWindowExceededError(ValueError):
    """Raised when estimated prompt tokens exceed MAX_CONTEXT_SIZE."""


def estimate_prompt_tokens(messages: list[dict[str, str]]) -> int:
    """Estimate total prompt tokens for a list of chat messages."""
    total_chars = sum(len(m.get("content", "")) for m in messages)
    return max(1, total_chars // 4)


def _is_daily_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "tokens per day",
            "requests per day",
            "daily token limit",
            "daily quota",
            "quota exceeded",
        )
    )


def _retry_after_seconds(exc: Exception) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    value = headers.get("retry-after")
    if value is None:
        return 2.0
    try:
        return min(10.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return 2.0


class GroqProvider:
    """Groq LLM provider with per-request usage tracking and resource limits."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-oss-20b",
        usage_tracker: UsageTracker | None = None,
        max_context_size: int | None = None,
    ) -> None:
        api_key = api_key or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file."
            )

        configured_context_limit = (
            max_context_size
            if max_context_size is not None
            else (
                int(os.getenv("MAX_CONTEXT_SIZE"))
                if os.getenv("MAX_CONTEXT_SIZE")
                else None
            )
        )
        if configured_context_limit is not None and configured_context_limit < 1:
            raise ValueError("max_context_size must be a positive integer.")

        self.client = AsyncGroq(api_key=api_key)
        self.model = model
        self.usage_tracker = usage_tracker or UsageTracker()
        self.max_context_size = configured_context_limit

    async def _create_completion(
        self,
        request: dict[str, Any],
        operation: str,
    ) -> Any:
        """Execute and measure one API request with bounded retries."""
        max_context = getattr(self, "max_context_size", None)
        messages = request.get("messages", [])

        if max_context is not None and messages:
            estimated = estimate_prompt_tokens(messages)
            if estimated > max_context:
                log_event(
                    "limit_violation",
                    level=logging.WARNING,
                    logger_name="app.llm",
                    limit="max_context_size",
                    estimated_prompt_tokens=estimated,
                    max_context_size=max_context,
                )
                try:
                    from app.observability.metrics import record_limit_violation

                    record_limit_violation("max_context_size")
                except Exception:
                    pass
                raise ContextWindowExceededError(
                    f"Estimated prompt tokens ({estimated}) exceed "
                    f"MAX_CONTEXT_SIZE ({max_context})."
                )

        tracker = get_active_usage_tracker() or self.usage_tracker

        for attempt in range(3):
            tracker.reserve_call()
            started_at = time.perf_counter()
            log_event(
                "llm_request_started",
                logger_name="app.llm",
                operation=operation,
                model=self.model,
            )
            try:
                response = await self.client.chat.completions.create(
                    **cast(Any, request)
                )
            except Exception as exc:
                duration = time.perf_counter() - started_at
                tracker.record(
                    operation=operation,
                    model=self.model,
                    duration_seconds=duration,
                    succeeded=False,
                )
                log_event(
                    "llm_request_failed",
                    level=logging.ERROR,
                    logger_name="app.llm",
                    operation=operation,
                    model=self.model,
                    duration_seconds=round(duration, 6),
                    exc_info=True,
                )
                retryable = isinstance(exc, groq.RateLimitError) or isinstance(
                    exc, groq.InternalServerError
                )
                if not retryable or _is_daily_quota_error(exc) or attempt == 2:
                    raise
                delay = _retry_after_seconds(exc) * (2**attempt)
                await asyncio.sleep(min(10.0, delay))
                continue

            duration = time.perf_counter() - started_at
            usage = getattr(response, "usage", None)

            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)

            tracker.record(
                operation=operation,
                model=self.model,
                duration_seconds=duration,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                succeeded=True,
            )
            log_event(
                "llm_request_completed",
                logger_name="app.llm",
                operation=operation,
                model=self.model,
                duration_seconds=round(duration, 6),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )

            return response

        raise RuntimeError("Unreachable: retry loop exhausted")

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }

        response = await self._create_completion(
            request=request,
            operation="generate",
        )

        return response.choices[0].message.content or ""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
    ) -> Any:
        schema = response_model.model_json_schema()

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "strict": False,
                "schema": schema,
            },
        }

        request_messages = list(messages)

        for attempt in range(2):
            request: dict[str, Any] = {
                "model": self.model,
                "messages": request_messages,
                "response_format": response_format,
            }

            response = await self._create_completion(
                request=request,
                operation="generate_structured",
            )

            content = response.choices[0].message.content or ""

            try:
                return response_model.model_validate_json(content)

            except ValidationError as exc:
                if attempt == 1:
                    raise

                request_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous response failed schema "
                            "validation. Return a corrected response "
                            "that strictly matches the required schema.\n\n"
                            f"Validation error:\n{exc}"
                        ),
                    }
                )

        raise RuntimeError("Structured generation exhausted retries.")