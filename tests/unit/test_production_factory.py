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

    with pytest.raises(ValueError) as exc:
        build_production_research_graph("test-research-id", None)

    for name in expected_missing:
        assert name in str(exc.value)
