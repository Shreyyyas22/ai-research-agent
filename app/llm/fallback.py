from __future__ import annotations

from typing import Any

from app.llm.base import LLMProvider


def _is_daily_quota_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(
        marker in msg
        for marker in (
            "tokens per day",
            "requests per day",
            "daily token limit",
            "daily quota",
            "quota exceeded",
        )
    )


class FallbackProvider:
    """Try primary LLM, fallback to secondary on daily quota exhaustion."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider) -> None:
        self.primary = primary
        self.fallback = fallback

    async def generate(self, messages, **kwargs: Any) -> str:
        try:
            return await self.primary.generate(messages, **kwargs)
        except Exception as exc:
            if _is_daily_quota_error(exc):
                return await self.fallback.generate(messages, **kwargs)
            raise

    async def generate_structured(self, messages, response_model, **kwargs: Any) -> Any:
        try:
            return await self.primary.generate_structured(messages, response_model, **kwargs)
        except Exception as exc:
            if _is_daily_quota_error(exc):
                return await self.fallback.generate_structured(messages, response_model, **kwargs)
            raise
