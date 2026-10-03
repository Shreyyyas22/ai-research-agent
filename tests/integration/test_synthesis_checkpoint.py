import pytest

from app.agents.graph import synthesize_findings
from app.schemas.research import Evidence, Source, SynthesisResult
from app.services.citation_service import CitationService


class FakeSynthesizer:
    async def synthesize(
        self,
        question,
        evidence,
        conflicts,
        llm_provider,
    ):
        return SynthesisResult(
            claims=[
                {
                    "claim": "PostgreSQL supports JSONB.",
                    "citation_ids": [1],
                },
                {
                    "claim": "MongoDB stores documents using BSON.",
                    "citation_ids": [2],
                },
            ]
        )


class FakeLLM:
    pass


def make_evidence():
    return [
        Evidence(
            source=Source(
                title="PostgreSQL Documentation",
                url="https://example.com/postgres",
            ),
            claim="PostgreSQL supports JSONB.",
            excerpt="PostgreSQL provides JSONB.",
        ),
        Evidence(
            source=Source(
                title="MongoDB Documentation",
                url="https://example.com/mongodb",
            ),
            claim="MongoDB stores documents using BSON.",
            excerpt="MongoDB stores BSON documents.",
        ),
    ]


@pytest.mark.asyncio
async def test_synthesis_checkpoint():
    state = {
        "question": "How do PostgreSQL and MongoDB store data?",
        "evidence": make_evidence(),
        "conflicts": [],
    }

    result = await synthesize_findings(
        state=state,
        synthesizer=FakeSynthesizer(),
        citation_service=CitationService(),
        llm_provider=FakeLLM(),
    )

    synthesis = result["findings"]

    assert isinstance(synthesis, SynthesisResult)
    assert len(synthesis.claims) == 2
    assert synthesis.claims[0].citation_ids == [1]
    assert synthesis.claims[1].citation_ids == [2]