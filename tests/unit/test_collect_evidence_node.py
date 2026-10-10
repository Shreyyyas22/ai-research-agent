import pytest

from app.agents.graph import collect_evidence
from app.schemas.research import Evidence, Source


class FakeWebFetchTool:
    def __init__(self, responses):
        self.responses = responses
        self.urls = []

    async def execute(self, input):
        url = input["url"]
        self.urls.append(url)
        return self.responses[url]


class FakeResearchService:
    def __init__(self):
        self.calls = []

    async def extract_evidence(
        self,
        source,
        content,
        llm_provider,
    ):
        self.calls.append((source, content, llm_provider))
        return [
            Evidence(
                source=source,
                claim=f"Claim from {source.title}",
                excerpt=content,
            )
        ]


@pytest.mark.asyncio
async def test_collect_evidence_fetches_and_extracts_new_sources():
    source = Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )
    failed_source = Source(
        title="Unavailable Source",
        url="https://example.com/unavailable",
    )
    fetch_tool = FakeWebFetchTool(
        {
            source.url: {
                "success": True,
                "content": "PostgreSQL supports vector data.",
            },
            failed_source.url: {
                "success": False,
                "content": "",
                "error": "HTTP 404: page not found.",
            },
        }
    )
    research_service = FakeResearchService()
    llm_provider = object()

    result = await collect_evidence(
        state={"sources": [source, failed_source]},
        web_fetch_tool=fetch_tool,
        research_service=research_service,
        llm_provider=llm_provider,
    )

    assert fetch_tool.urls == [source.url, failed_source.url]
    assert research_service.calls == [
        (
            source,
            "PostgreSQL supports vector data.",
            llm_provider,
        )
    ]
    assert result["evidence"] == [
        Evidence(
            source=source,
            claim="Claim from PostgreSQL Documentation",
            excerpt="PostgreSQL supports vector data.",
        )
    ]


@pytest.mark.asyncio
async def test_collect_evidence_preserves_and_does_not_refetch_existing_evidence():
    source = Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )
    existing_evidence = Evidence(
        source=source,
        claim="PostgreSQL supports vector search.",
        excerpt="PostgreSQL can store vector data.",
    )
    fetch_tool = FakeWebFetchTool({})
    research_service = FakeResearchService()

    result = await collect_evidence(
        state={
            "sources": [source],
            "evidence": [existing_evidence],
        },
        web_fetch_tool=fetch_tool,
        research_service=research_service,
        llm_provider=object(),
    )

    assert fetch_tool.urls == []
    assert research_service.calls == []
    assert result["evidence"] == [existing_evidence]
