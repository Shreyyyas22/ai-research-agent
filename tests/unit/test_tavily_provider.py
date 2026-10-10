from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.tools.tavily_provider import TavilySearchProvider


@pytest.mark.asyncio
async def test_search_maps_tavily_results():
    provider = TavilySearchProvider(api_key="test-key")

    mock_response = AsyncMock()
    mock_response.raise_for_status = lambda: None
    mock_response.json = lambda: {
        "results": [
            {
                "title": "PostgreSQL Vector Search",
                "url": "https://example.com/vector-search",
                "content": "PostgreSQL supports vector search through extensions.",
            }
        ]
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.return_value = mock_response

    with patch(
        "app.tools.tavily_provider.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await provider.search("PostgreSQL vector search")

    assert result.success is True
    assert len(result.results) == 1
    assert result.results[0].title == "PostgreSQL Vector Search"
    assert result.results[0].url == "https://example.com/vector-search"
    assert "vector search" in result.results[0].snippet


@pytest.mark.asyncio
async def test_search_without_api_key_returns_error():
    with patch.dict("os.environ", {"TAVILY_API_KEY": ""}):
        provider = TavilySearchProvider(api_key="")

        result = await provider.search("test query")

    assert result.success is False
    assert result.results == []
    assert result.error == "TAVILY_API_KEY is not configured"


@pytest.mark.asyncio
async def test_search_handles_http_error():
    provider = TavilySearchProvider(api_key="test-key")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.post.side_effect = httpx.ConnectError(
        "connection failed"
    )

    with patch(
        "app.tools.tavily_provider.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = await provider.search("test query")

    assert result.success is False
    assert result.results == []
    assert result.error == "Tavily search failed: ConnectError"
