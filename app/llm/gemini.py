from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

from app.llm.usage import get_active_usage_tracker
from app.observability.logging import log_event

load_dotenv()


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


class GeminiProvider:
    """Gemini 3.8 Flash via Interactions API (httpx, no extra SDK)."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-3.5-flash-lite",
        timeout: float = 60.0,
    ) -> None:
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "x-goog-api-key": self.api_key}

    def _url(self) -> str:
        return "https://generativelanguage.googleapis.com/v1beta/interactions"

    def _messages_to_input(self, messages: list[dict[str, str]]) -> str:
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                parts.append(f"System: {content}")
            else:
                parts.append(content)
        return "\n\n".join(parts)

    async def _call_interactions(
        self,
        input_text: str,
        response_schema: dict[str, Any] | None = None,
        thinking_level: str = "medium",
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_text,
        }
        if response_schema is not None:
            payload["input"] = input_text + "\n\nRespond with valid JSON matching the required schema."
            payload["generation_config"] = {"thinking_level": thinking_level}

        for attempt in range(3):
            started_at = time.perf_counter()
            tracker = get_active_usage_tracker()
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(self._url(), headers=self._headers(), json=payload)
                    resp.raise_for_status()
                    data = resp.json()

                duration = time.perf_counter() - started_at
                text = ""
                if isinstance(data, dict):
                    steps = data.get("steps", [])
                    if steps:
                        for step in reversed(steps):
                            if step.get("type") == "model_output":
                                content = step.get("content", [])
                                if content and isinstance(content, list):
                                    text = "".join(p.get("text", "") for p in content if isinstance(p, dict))
                                    if text:
                                        break
                                elif isinstance(content, str):
                                    text = content
                                    break
                    if not text and "interaction" in data:
                        inter = data["interaction"]
                        text = inter.get("output_text") or inter.get("outputText") or ""
                        if not text and "output" in inter:
                            text = str(inter["output"])
                    if not text:
                        text = data.get("output_text") or data.get("outputText") or ""
                        if isinstance(data.get("output"), dict):
                            text = data["output"].get("text", "") or text
                    if not text:
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text = "".join(p.get("text", "") for p in parts)
                        else:
                            text = data.get("text", "") or ""
                if not text and isinstance(data, dict):
                    import json as _json
                    text = _json.dumps(data)[:2000] if data else ""

                if tracker is not None:
                    prompt_tokens = len(input_text) // 4
                    completion_tokens = len(text) // 4 if text else 0
                    tracker.record(
                        operation="generate_structured" if response_schema else "generate",
                        model=self.model,
                        duration_seconds=duration,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        succeeded=True,
                    )
                log_event(
                    "llm_request_completed",
                    logger_name="app.llm",
                    operation="generate_structured" if response_schema else "generate",
                    model=self.model,
                    duration_seconds=round(duration, 6),
                )
                return text or ""
            except Exception as exc:
                duration = time.perf_counter() - started_at
                if tracker is not None:
                    tracker.record(
                        operation="generate_structured" if response_schema else "generate",
                        model=self.model,
                        duration_seconds=duration,
                        succeeded=False,
                    )
                log_event(
                    "llm_request_failed",
                    logger_name="app.llm",
                    operation="generate_structured" if response_schema else "generate",
                    model=self.model,
                    duration_seconds=round(duration, 6),
                    exc_info=True,
                )
                # Retry on 429/503 unless daily quota
                status = getattr(getattr(exc, "response", None), "status_code", None)
                retryable = status in (429, 503) or "rate limit" in str(exc).lower() or "503" in str(exc)
                if not retryable or _is_daily_quota_error(exc) or attempt == 2:
                    raise
                delay = _retry_after_seconds(exc) * (2**attempt)
                await asyncio.sleep(min(10.0, delay))
                continue

        raise RuntimeError("Unreachable: retry loop exhausted")

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        input_text = self._messages_to_input(messages)
        text = await self._call_interactions(input_text)
        return text or ""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
    ) -> Any:
        schema = response_model.model_json_schema()
        input_text = self._messages_to_input(messages)
        schema_hint = f"\n\nYou must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        full_input = input_text + schema_hint

        request_input = full_input
        for attempt in range(2):
            text = await self._call_interactions(request_input, response_schema=schema)
            content = text or ""
            if content.strip().startswith("```"):
                lines = content.strip().splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines)

            try:
                return response_model.model_validate_json(content)
            except ValidationError as exc:
                if attempt == 1:
                    raise
                request_input = full_input + (
                    "\n\nThe previous response failed schema validation. Return a corrected response "
                    f"that strictly matches the required schema.\n\nValidation error:\n{exc}"
                )
        raise RuntimeError("Structured generation exhausted retries")
