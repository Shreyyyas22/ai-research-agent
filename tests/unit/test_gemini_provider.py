import pytest
from unittest.mock import AsyncMock, patch

import httpx

from app.llm.gemini import GeminiProvider


def _make_gemini_response(text: str):
    return {
        "id": "test-id",
        "status": "completed",
        "steps": [{"type": "model_output", "content": [{"text": text}]}],
    }


@pytest.mark.asyncio
async def test_gemini_generate_retries_on_429_then_succeeds():
    provider = GeminiProvider(api_key="test-key")

    # First call 429, second succeeds - mock post to raise directly
    mock_resp_success = AsyncMock()
    mock_resp_success.raise_for_status = lambda: None
    mock_resp_success.json = lambda: _make_gemini_response("hello")

    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value.post.return_value = mock_resp_success

    async def fail_post(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "429", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(429, headers={"retry-after": "1"}, request=httpx.Request("POST", "https://example.com"))
        )

    mock_client_fail = AsyncMock()
    mock_client_fail.__aenter__.return_value.post = AsyncMock(side_effect=fail_post)

    with patch("app.llm.gemini.httpx.AsyncClient", side_effect=[mock_client_fail, mock_client_success]):
        with patch("app.llm.gemini.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await provider.generate([{"role": "user", "content": "hi"}])
            assert result == "hello"
            mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_gemini_daily_quota_fails_fast():
    provider = GeminiProvider(api_key="test-key")

    async def fail_post(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "tokens per day Limit 200000",
            request=httpx.Request("POST", "https://example.com"),
            response=httpx.Response(429, request=httpx.Request("POST", "https://example.com")),
        )

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post = AsyncMock(side_effect=fail_post)

    with patch("app.llm.gemini.httpx.AsyncClient", return_value=mock_client):
        with patch("app.llm.gemini.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            with pytest.raises(httpx.HTTPStatusError):
                await provider.generate([{"role": "user", "content": "hi"}])
            mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_gemini_generate_structured_retries_on_503():
    from pydantic import BaseModel

    class DummyModel(BaseModel):
        answer: str

    provider = GeminiProvider(api_key="test-key")

    mock_resp_success = AsyncMock()
    mock_resp_success.raise_for_status = lambda: None
    mock_resp_success.json = lambda: _make_gemini_response('{"answer": "42"}')
    mock_client_success = AsyncMock()
    mock_client_success.__aenter__.return_value.post.return_value = mock_resp_success

    async def fail_post(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "503", request=httpx.Request("POST", "https://example.com"), response=httpx.Response(503, request=httpx.Request("POST", "https://example.com"))
        )

    mock_client_fail = AsyncMock()
    mock_client_fail.__aenter__.return_value.post = AsyncMock(side_effect=fail_post)

    with patch("app.llm.gemini.httpx.AsyncClient", side_effect=[mock_client_fail, mock_client_success]):
        with patch("app.llm.gemini.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.generate_structured([{"role": "user", "content": "hi"}], DummyModel)
            assert result.answer == "42"
