import pytest

from app.schemas.research import Evidence, Source, SourceEvaluation
from app.services.source_evaluation_service import SourceEvaluationService


class FakeEvaluationLLM:
    async def generate_structured(
        self,
        messages,
        response_model,
    ):
        assert response_model is SourceEvaluation

        return SourceEvaluation(
            sufficiency={
                "sufficient": True,
                "reasoning": "The evidence covers the main research question.",
                "missing_information": [],
            },
            conflicts=[
                {
                    "claim_a": "PostgreSQL performs better for workload A.",
                    "claim_b": "MongoDB performs better for workload A.",
                    "possible_explanation": (
                        "The sources may have used different workloads."
                    ),
                    "confidence": "medium",
                }
            ],
        )


class FailingEvaluationLLM:
    async def generate_structured(
        self,
        messages,
        response_model,
    ):
        raise AssertionError(
            "LLM should not be called when evidence is empty."
        )


def make_evidence(
    claim: str,
    excerpt: str,
    url: str,
) -> Evidence:
    return Evidence(
        source=Source(
            title="Test Source",
            url=url,
        ),
        claim=claim,
        excerpt=excerpt,
    )


@pytest.mark.asyncio
async def test_evaluate_returns_structured_evaluation():
    service = SourceEvaluationService()

    evidence = [
        make_evidence(
            claim="PostgreSQL performs better for workload A.",
            excerpt="Benchmark result A.",
            url="https://example.com/postgres",
        ),
        make_evidence(
            claim="MongoDB performs better for workload A.",
            excerpt="Benchmark result B.",
            url="https://example.com/mongodb",
        ),
    ]

    result = await service.evaluate(
        question="Which database performs better for workload A?",
        evidence=evidence,
        llm_provider=FakeEvaluationLLM(),
    )

    assert result.sufficiency.sufficient is True
    assert len(result.conflicts) == 1
    assert result.conflicts[0].confidence == "medium"


@pytest.mark.asyncio
async def test_evaluate_handles_empty_evidence_without_llm():
    service = SourceEvaluationService()

    result = await service.evaluate(
        question="Which database should be used?",
        evidence=[],
        llm_provider=FailingEvaluationLLM(),
    )

    assert result.sufficiency.sufficient is False
    assert result.conflicts == []
    assert result.sufficiency.missing_information == [
        "Relevant supporting evidence"
    ]


@pytest.mark.asyncio
async def test_evaluate_rejects_empty_question():
    service = SourceEvaluationService()

    with pytest.raises(ValueError, match="Research question cannot be empty"):
        await service.evaluate(
            question="   ",
            evidence=[],
            llm_provider=FailingEvaluationLLM(),
        )