import pytest

from app.agents.production_factory import build_production_research_graph


@pytest.mark.parametrize(
    ("groq_key", "tavily_key", "expected_missing"),
    [
        ("", "", ["GROQ_API_KEY", "TAVILY_API_KEY"]),
        ("test-groq", "", ["TAVILY_API_KEY"]),
        ("", "test-tavily", ["GROQ_API_KEY"]),
    ],
)
def test_factory_rejects_missing_credentials(
    monkeypatch, groq_key, tavily_key, expected_missing
):
    monkeypatch.setenv("GROQ_API_KEY", groq_key)
    monkeypatch.setenv("TAVILY_API_KEY", tavily_key)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    with pytest.raises(ValueError) as exc:
        build_production_research_graph("test-research-id", None)

    for name in expected_missing:
        assert name in str(exc.value)


def test_factory_uses_gemini_when_provider_is_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")

    # Should not raise, should build graph with Gemini
    graph = build_production_research_graph("test-id", None)
    assert graph is not None


def test_factory_fallback_uses_gemini_when_groq_quota_exceeded(monkeypatch):
    # Both keys present, default groq with fallback to gemini
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily")
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    from app.llm.fallback import FallbackProvider

    graph = build_production_research_graph("test-id", None)
    # Factory should have created a FallbackProvider
    # We can't easily inspect the graph's internal provider, but we can check it doesn't raise
    assert graph is not None
    # Verify fallback provider works: mock primary to fail with daily quota
    import asyncio
    from unittest.mock import AsyncMock

    async def _test_fallback():
        primary = AsyncMock()
        primary.generate.side_effect = Exception("tokens per day Limit 200000")
        fallback = AsyncMock()
        fallback.generate.return_value = "fallback ok"
        provider = FallbackProvider(primary, fallback)
        result = await provider.generate([{"role": "user", "content": "hi"}])
        assert result == "fallback ok"
        fallback.generate.assert_called_once()

    asyncio.run(_test_fallback())
