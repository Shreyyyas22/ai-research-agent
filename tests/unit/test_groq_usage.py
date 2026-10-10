from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import groq
import httpx
import pytest
from pydantic import BaseModel

from app.llm.groq import GroqProvider
from app.llm.usage import UsageTracker, use_usage_tracker


def make_response(content, prompt_tokens=100, completion_tokens=20):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ],
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        ),
    )


def make_provider(tracker=None):
    provider = GroqProvider.__new__(GroqProvider)
    provider.model = "test-model"
    provider.usage_tracker = tracker or UsageTracker()
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock()
            )
        )
    )
    return provider


@pytest.mark.asyncio
async def test_generate_records_usage():
    provider = make_provider()
    provider.client.chat.completions.create.return_value = make_response(
        "Hello"
    )

    result = await provider.generate(
        [{"role": "user", "content": "Hi"}]
    )

    snapshot = provider.usage_tracker.snapshot()

    assert result == "Hello"
    assert snapshot["llm_calls"] == 1
    assert snapshot["prompt_tokens"] == 100
    assert snapshot["completion_tokens"] == 20
    assert snapshot["successful_llm_calls"] == 1


class ExampleOutput(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_structured_generation_records_usage():
    provider = make_provider()
    provider.client.chat.completions.create.return_value = make_response(
        '{"answer": "42"}'
    )

    result = await provider.generate_structured(
        [{"role": "user", "content": "Answer"}],
        ExampleOutput,
    )

    snapshot = provider.usage_tracker.snapshot()

    assert result.answer == "42"
    assert snapshot["llm_calls"] == 1
    assert snapshot["total_tokens"] == 120


@pytest.mark.asyncio
async def test_structured_retry_counts_both_api_requests():
    provider = make_provider()
    provider.client.chat.completions.create.side_effect = [
        make_response('{"answer": 42}'),
        make_response('{"answer": "42"}'),
    ]

    result = await provider.generate_structured(
        [{"role": "user", "content": "Answer"}],
        ExampleOutput,
    )

    snapshot = provider.usage_tracker.snapshot()

    assert result.answer == "42"
    assert snapshot["llm_calls"] == 2
    assert snapshot["prompt_tokens"] == 200
    assert snapshot["completion_tokens"] == 40


@pytest.mark.asyncio
async def test_failed_request_is_recorded_and_reraised():
    provider = make_provider()
    provider.client.chat.completions.create.side_effect = RuntimeError(
        "Provider unavailable"
    )

    with pytest.raises(RuntimeError, match="Provider unavailable"):
        await provider.generate(
            [{"role": "user", "content": "Hi"}]
        )

    snapshot = provider.usage_tracker.snapshot()

    assert snapshot["llm_calls"] == 1
    assert snapshot["failed_llm_calls"] == 1
    assert snapshot["successful_llm_calls"] == 0


from app.llm.groq import ContextWindowExceededError, estimate_prompt_tokens


@pytest.mark.asyncio
async def test_active_tracker_is_isolated_from_provider_tracker():
    provider = make_provider()
    provider.client.chat.completions.create.return_value = make_response(
        "Hello"
    )

    run_tracker = UsageTracker()

    with use_usage_tracker(run_tracker):
        await provider.generate(
            [{"role": "user", "content": "Hi"}]
        )

    assert run_tracker.snapshot()["llm_calls"] == 1
    assert provider.usage_tracker.snapshot()["llm_calls"] == 0

    # After the context exits, the provider's default tracker is restored.
    await provider.generate(
        [{"role": "user", "content": "Hi again"}]
    )

    assert run_tracker.snapshot()["llm_calls"] == 1
    assert provider.usage_tracker.snapshot()["llm_calls"] == 1


def test_estimate_prompt_tokens():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing."},
    ]
    tokens = estimate_prompt_tokens(messages)
    assert tokens > 0


@pytest.mark.asyncio
async def test_provider_raises_error_when_prompt_exceeds_max_context_size():
    provider = make_provider()
    provider.max_context_size = 5

    large_message = [{"role": "user", "content": "A" * 100}]

    with pytest.raises(ContextWindowExceededError) as exc_info:
        await provider.generate(large_message)

    assert "exceed MAX_CONTEXT_SIZE" in str(exc_info.value)


def _make_rate_limit_error(message: str, retry_after: str | None = None) -> groq.RateLimitError:
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(429, headers=headers, request=httpx.Request("POST", "https://api.groq.com"))
    return groq.RateLimitError(message=message, response=response, body=None)


def _make_server_error() -> groq.InternalServerError:
    response = httpx.Response(503, request=httpx.Request("POST", "https://api.groq.com"))
    return groq.InternalServerError(message="Service unavailable", response=response, body=None)


def _make_bad_request_error() -> groq.APIStatusError:
    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com"))
    return groq.APIStatusError(message="Bad request", response=response, body=None)


@pytest.mark.asyncio
async def test_transient_rate_limit_retries_then_succeeds():
    provider = make_provider()
    error = _make_rate_limit_error("Rate limit reached for model", retry_after="1")
    provider.client.chat.completions.create.side_effect = [error, make_response("ok")]

    with patch("app.llm.groq.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await provider.generate([{"role": "user", "content": "Hi"}])

    assert result == "ok"
    assert provider.client.chat.completions.create.call_count == 2
    mock_sleep.assert_called_once()
    # first retry: 1 * 2**0 = 1
    assert mock_sleep.call_args[0][0] == 1.0
    assert provider.usage_tracker.snapshot()["llm_calls"] == 2
    assert provider.usage_tracker.snapshot()["failed_llm_calls"] == 1
    assert provider.usage_tracker.snapshot()["successful_llm_calls"] == 1


@pytest.mark.asyncio
async def test_three_transient_failures_raise_after_three_attempts():
    provider = make_provider()
    error = _make_rate_limit_error("Rate limit reached", retry_after="1")
    provider.client.chat.completions.create.side_effect = [error, error, error]

    with patch("app.llm.groq.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(groq.RateLimitError):
            await provider.generate([{"role": "user", "content": "Hi"}])

    assert provider.client.chat.completions.create.call_count == 3
    assert provider.usage_tracker.snapshot()["failed_llm_calls"] == 3


@pytest.mark.asyncio
async def test_daily_quota_exhausted_fails_fast_without_retry():
    provider = make_provider()
    error = _make_rate_limit_error("Rate limit reached for model: tokens per day Limit 200000", retry_after="10")
    provider.client.chat.completions.create.side_effect = error

    with patch("app.llm.groq.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(groq.RateLimitError):
            await provider.generate([{"role": "user", "content": "Hi"}])

    assert provider.client.chat.completions.create.call_count == 1
    mock_sleep.assert_not_called()
    assert provider.usage_tracker.snapshot()["failed_llm_calls"] == 1


@pytest.mark.asyncio
async def test_non_retryable_400_fails_immediately():
    provider = make_provider()
    error = _make_bad_request_error()
    provider.client.chat.completions.create.side_effect = error

    with patch("app.llm.groq.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(groq.APIStatusError):
            await provider.generate([{"role": "user", "content": "Hi"}])

    assert provider.client.chat.completions.create.call_count == 1
    mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_retry_backoff_is_capped_at_ten_seconds():
    provider = make_provider()
    error = _make_rate_limit_error("Rate limit", retry_after="8")
    provider.client.chat.completions.create.side_effect = [error, error, make_response("ok")]

    with patch("app.llm.groq.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await provider.generate([{"role": "user", "content": "Hi"}])

    assert result == "ok"
    # attempt 0: 8*1=8, attempt1: 8*2=16 -> capped to 10
    assert mock_sleep.call_args_list[0][0][0] == 8.0
    assert mock_sleep.call_args_list[1][0][0] == 10.0


