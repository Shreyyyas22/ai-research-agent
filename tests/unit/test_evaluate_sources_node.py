import pytest

from app.agents.graph import evaluate_sources
from app.schemas.research import (
    Evidence,
    Source,
    SourceEvaluation,
)
from app.services.source_evaluation_service import (
    SourceEvaluationService,
)


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
                "reasoning": "The evidence sufficiently answers the question.",
                "missing_information": [],
            },
            conflicts=[
                {
                    "claim_a": "Claim from source A.",
                    "claim_b": "Contradictory claim from source B.",
                    "possible_explanation": "Different research conditions.",
                    "confidence": "medium",
                }
            ],
        )


@pytest.mark.asyncio
async def test_evaluate_sources_updates_research_state():
    evidence = [
        Evidence(
            source=Source(
                title="Source A",
                url="https://example.com/a",
            ),
            claim="Claim from source A.",
            excerpt="Supporting text A.",
        ),
        Evidence(
            source=Source(
                title="Source B",
                url="https://example.com/b",
            ),
            claim="Contradictory claim from source B.",
            excerpt="Supporting text B.",
        ),
    ]

    state = {
        "question": "Which claim is supported?",
        "evidence": evidence,
    }

    result = await evaluate_sources(
        state=state,
        evaluation_service=SourceEvaluationService(),
        llm_provider=FakeEvaluationLLM(),
    )

    assert result["research_sufficient"] is True
    assert len(result["conflicts"]) == 1
    assert result["conflicts"][0].confidence == "medium"


@pytest.mark.asyncio
async def test_evaluate_sources_marks_empty_evidence_insufficient():
    state = {
        "question": "Which database should be used?",
        "evidence": [],
    }

    result = await evaluate_sources(
        state=state,
        evaluation_service=SourceEvaluationService(),
        llm_provider=FakeEvaluationLLM(),
    )

    assert result["research_sufficient"] is False
    assert result["conflicts"] == []