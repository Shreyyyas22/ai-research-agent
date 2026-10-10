import pytest

from app.schemas.research import EvidenceExtraction, Source
from app.services.research_service import ResearchService


class FakeEvidenceLLM:
    async def generate_structured(
        self,
        messages,
        response_model,
    ):
        assert response_model is EvidenceExtraction

        return EvidenceExtraction(
            evidence=[
                {
                    "claim": "PostgreSQL supports transactions.",
                    "excerpt": "PostgreSQL provides full transaction support.",
                },
                {
                    "claim": "PostgreSQL supports indexing.",
                    "excerpt": "PostgreSQL provides several index types.",
                },
            ]
        )


@pytest.mark.asyncio
async def test_extract_evidence_attaches_original_source():
    service = ResearchService()

    source = Source(
        title="PostgreSQL Documentation",
        url="https://postgresql.org/docs/",
    )

    content = """
    PostgreSQL provides full transaction support.
    PostgreSQL provides several index types.
    """

    llm = FakeEvidenceLLM()

    evidence = await service.extract_evidence(
        source=source,
        content=content,
        llm_provider=llm,
    )

    assert len(evidence) == 2

    assert evidence[0].claim == "PostgreSQL supports transactions."
    assert (
        evidence[0].excerpt
        == "PostgreSQL provides full transaction support."
    )

    assert evidence[0].source.title == source.title
    assert evidence[0].source.url == source.url


@pytest.mark.asyncio
async def test_extract_evidence_returns_empty_for_empty_content():
    service = ResearchService()

    source = Source(
        title="PostgreSQL Documentation",
        url="https://postgresql.org/docs/",
    )

    llm = FakeEvidenceLLM()

    evidence = await service.extract_evidence(
        source=source,
        content="",
        llm_provider=llm,
    )

    assert evidence == []


@pytest.mark.asyncio
async def test_extract_evidence_truncates_oversized_content():
    service = ResearchService()
    source = Source(
        title="PostgreSQL Documentation",
        url="https://postgresql.org/docs/",
    )
    content = "A" * 10_000

    class CapturingLLM:
        async def generate_structured(self, messages, response_model):
            assert response_model is EvidenceExtraction
            for message in messages:
                if "<untrusted_source_content>" in message["content"]:
                    content_part = message["content"].split(
                        "<untrusted_source_content>\n"
                    )[1].split("\n</untrusted_source_content>")[0]
                    assert len(content_part) <= 6000
            return EvidenceExtraction(evidence=[])

    await service.extract_evidence(
        source=source,
        content=content,
        llm_provider=CapturingLLM(),
    )