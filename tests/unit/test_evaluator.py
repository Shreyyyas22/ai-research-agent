import pytest

from app.agents.evaluator import ReportEvaluator
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


class FakeLLMProvider:
    def __init__(self, evaluation: ReportEvaluation) -> None:
        self.evaluation = evaluation
        self.messages = None
        self.response_model = None

    async def generate_structured(
        self,
        messages,
        response_model,
        **kwargs,
    ):
        self.messages = messages
        self.response_model = response_model
        return self.evaluation


def build_evidence() -> list[Evidence]:
    return [
        Evidence(
            source=Source(
                title="PostgreSQL Documentation",
                url="https://example.com/postgresql",
            ),
            claim="PostgreSQL supports vector data through extensions.",
            excerpt="PostgreSQL can store vector representations using extensions.",
        )
    ]


def build_report() -> ResearchReport:
    return ResearchReport(
        title="Research Report: Vector Databases",
        executive_summary=(
            "PostgreSQL can store vector representations."
        ),
        key_findings=[
            SynthesizedClaim(
                claim="PostgreSQL supports vector data through extensions.",
                citation_ids=[1],
            )
        ],
        detailed_analysis=(
            "The supplied evidence indicates that PostgreSQL "
            "can store vector representations."
        ),
        trade_offs=[],
        evidence=build_evidence(),
        limitations=[],
        conclusion=(
            "PostgreSQL can store vector representations."
        ),
        sources=[
            Source(
                title="PostgreSQL Documentation",
                url="https://example.com/postgresql",
            )
        ],
    )


@pytest.mark.asyncio
async def test_evaluator_returns_structured_evaluation():
    expected = ReportEvaluation(
        grounded=True,
        citation_correct=True,
        hallucination_detected=False,
        score=5,
        reasoning="All important claims are supported by the evidence.",
        unsupported_claims=[],
    )

    llm_provider = FakeLLMProvider(expected)
    evaluator = ReportEvaluator()

    result = await evaluator.evaluate(
        question="Can PostgreSQL store vector data?",
        report=build_report(),
        evidence=build_evidence(),
        llm_provider=llm_provider,
    )

    assert result == expected
    assert llm_provider.response_model is ReportEvaluation


@pytest.mark.asyncio
async def test_evaluator_prompt_contains_report_and_evidence():
    expected = ReportEvaluation(
        grounded=True,
        citation_correct=True,
        hallucination_detected=False,
        score=5,
        reasoning="Supported.",
        unsupported_claims=[],
    )

    llm_provider = FakeLLMProvider(expected)
    evaluator = ReportEvaluator()

    await evaluator.evaluate(
        question="Can PostgreSQL store vector data?",
        report=build_report(),
        evidence=build_evidence(),
        llm_provider=llm_provider,
    )

    assert llm_provider.messages is not None

    user_message = llm_provider.messages[1]["content"]

    assert "Can PostgreSQL store vector data?" in user_message
    assert "PostgreSQL supports vector data through extensions." in user_message
    assert "PostgreSQL Documentation" in user_message
    assert "https://example.com/postgresql" in user_message


@pytest.mark.asyncio
async def test_evaluator_rejects_empty_question():
    llm_provider = FakeLLMProvider(
        ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning="Supported.",
            unsupported_claims=[],
        )
    )

    evaluator = ReportEvaluator()

    with pytest.raises(ValueError, match="Research question cannot be empty"):
        await evaluator.evaluate(
            question="   ",
            report=build_report(),
            evidence=build_evidence(),
            llm_provider=llm_provider,
        )


@pytest.mark.asyncio
async def test_evaluator_rejects_missing_evidence():
    llm_provider = FakeLLMProvider(
        ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning="Supported.",
            unsupported_claims=[],
        )
    )

    evaluator = ReportEvaluator()

    with pytest.raises(
        ValueError,
        match="Cannot evaluate a report without evidence",
    ):
        await evaluator.evaluate(
            question="Can PostgreSQL store vector data?",
            report=build_report(),
            evidence=[],
            llm_provider=llm_provider,
        )