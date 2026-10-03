import pytest

from app.schemas.research import Evidence, Source
from app.services.source_evaluation_service import SourceEvaluationService


class FakeConflictLLM:
    async def generate_structured(self, messages, response_model, **kwargs):
        return response_model(
            sufficiency={
                "sufficient": True,
                "reasoning": "Both sources address the research question, but they disagree on the reported result.",
                "missing_information": [],
            },
            conflicts=[
                {
                    "claim_a": "Source A reports that PostgreSQL is faster for the workload.",
                    "claim_b": "Source B reports that MongoDB is faster for the workload.",
                    "possible_explanation": (
                        "The sources may have used different datasets, workloads, "
                        "configurations, or benchmark methodologies."
                    ),
                    "confidence": "high",
                }
            ],
        )


@pytest.mark.asyncio
async def test_conflicting_sources_are_surfaced_instead_of_resolved():
    service = SourceEvaluationService()

    evidence = [
        Evidence(
            source=Source(
                title="Benchmark Source A",
                url="https://example.com/source-a",
            ),
            claim="PostgreSQL is faster for the workload.",
            excerpt="The benchmark reports PostgreSQL completing the workload faster.",
        ),
        Evidence(
            source=Source(
                title="Benchmark Source B",
                url="https://example.com/source-b",
            ),
            claim="MongoDB is faster for the workload.",
            excerpt="The benchmark reports MongoDB completing the workload faster.",
        ),
    ]

    result = await service.evaluate(
        question="Which database is faster for this workload?",
        evidence=evidence,
        llm_provider=FakeConflictLLM(),
    )

    assert result.sufficiency.sufficient is True
    assert len(result.conflicts) == 1

    conflict = result.conflicts[0]

    assert "PostgreSQL" in conflict.claim_a
    assert "MongoDB" in conflict.claim_b
    assert conflict.possible_explanation
    assert conflict.confidence == "high"