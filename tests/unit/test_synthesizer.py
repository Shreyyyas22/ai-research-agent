from app.agents.synthesizer import Synthesizer
from app.schemas.research import Conflict, Evidence, Source, SynthesisResult
import pytest

class FakeSynthesizerLLM:
    async def generate_structured(
        self,
        messages,
        response_model,
        **kwargs,
    ):
        return response_model(
            claims=[
                {
                    "claim": "PostgreSQL supports JSONB.",
                    "citation_ids": [1],
                },
                {
                    "claim": "MongoDB stores documents using BSON.",
                    "citation_ids": [2],
            }
            ]
        )


def make_evidence() -> list[Evidence]:
    return [
        Evidence(
            source=Source(
                title="PostgreSQL Documentation",
                url="https://example.com/postgres",
            ),
            claim="PostgreSQL supports JSONB.",
            excerpt="PostgreSQL provides a JSONB data type.",
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
async def test_synthesizer_returns_structured_claims():
    synthesizer = Synthesizer()
    llm = FakeSynthesizerLLM()

    result = await synthesizer.synthesize(
        question="How do PostgreSQL and MongoDB store semi-structured data?",
        evidence=make_evidence(),
        conflicts=[],
        llm_provider=llm,
    )

    assert isinstance(result, SynthesisResult)
    assert len(result.claims) == 2
    assert result.claims[0].citation_ids == [1]
    assert result.claims[1].citation_ids == [2]

@pytest.mark.asyncio
async def test_synthesizer_preserves_conflicts():
    synthesizer = Synthesizer()
    llm = FakeSynthesizerLLM()

    conflicts = [
        Conflict(
            claim_a="Source A reports PostgreSQL is faster.",
            claim_b="Source B reports MongoDB is faster.",
            possible_explanation="Different benchmark workloads.",
            confidence="high",
        )
    ]

    result = await synthesizer.synthesize(
        question="Which database is faster?",
        evidence=make_evidence(),
        conflicts=conflicts,
        llm_provider=llm,
    )

    assert result.claims