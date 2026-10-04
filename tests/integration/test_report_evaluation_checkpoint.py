import pytest

from app.agents.graph import build_research_graph
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    Source,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.citation_service import CitationService
from app.services.report_service import ReportService


class FakeEvaluationService:
    async def evaluate(
        self,
        question,
        evidence,
        llm_provider,
    ):
        from app.schemas.research import (
            EvidenceSufficiency,
            SourceEvaluation,
        )

        return SourceEvaluation(
            sufficiency=EvidenceSufficiency(
                sufficient=True,
                reasoning="The supplied evidence is sufficient.",
                missing_information=[],
            ),
            conflicts=[],
        )


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
                SynthesizedClaim(
                    claim="PostgreSQL supports vector search.",
                    citation_ids=[1],
                )
            ]
        )


class FakeReportEvaluator:
    def __init__(self, evaluations):
        self.evaluations = list(evaluations)
        self.call_count = 0

    async def evaluate(
        self,
        question,
        report,
        evidence,
        llm_provider,
    ):
        evaluation = self.evaluations[
            min(
                self.call_count,
                len(self.evaluations) - 1,
            )
        ]

        self.call_count += 1

        return evaluation


def build_evidence() -> list[Evidence]:
    source = Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )

    return [
        Evidence(
            source=source,
            claim="PostgreSQL supports vector search.",
            excerpt="PostgreSQL can store and query vector data.",
        )
    ]


def build_source() -> Source:
    return Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )


def build_initial_state() -> dict:
    return {
        "question": "Does PostgreSQL support vector search?",
        "evidence": build_evidence(),
        "sources": [build_source()],
        "plan": None,
        "research_tasks": [],
    }


@pytest.mark.asyncio
async def test_unsupported_claim_is_flagged_by_report_evaluator():
    unsupported_claim = ReportEvaluation(
        grounded=False,
        citation_correct=False,
        hallucination_detected=True,
        score=2,
        reasoning=(
            "The report contains a claim that is not supported "
            "by the supplied evidence."
        ),
        unsupported_claims=[
            "PostgreSQL is 50% faster than MongoDB."
        ],
    )

    valid_evaluation = ReportEvaluation(
        grounded=True,
        citation_correct=True,
        hallucination_detected=False,
        score=5,
        reasoning="All claims are supported.",
        unsupported_claims=[],
    )

    report_evaluator = FakeReportEvaluator(
        [
            unsupported_claim,
            valid_evaluation,
        ]
    )

    graph = build_research_graph(
        evaluation_service=FakeEvaluationService(),
        llm_provider=None,
        synthesizer=FakeSynthesizer(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=report_evaluator,
        max_evaluation_iterations=2,
    )

    result = await graph.ainvoke(
        build_initial_state()
    )

    assert report_evaluator.call_count == 2

    assert result["report_evaluation"].grounded is True
    assert result["report_evaluation"].hallucination_detected is False
    assert result["report_evaluation"].score == 5

    assert result["evaluation_iteration"] == 2


@pytest.mark.asyncio
async def test_report_evaluation_stops_at_max_iterations():
    low_evaluation = ReportEvaluation(
        grounded=False,
        citation_correct=False,
        hallucination_detected=True,
        score=2,
        reasoning="The report contains unsupported claims.",
        unsupported_claims=[
            "Unsupported factual claim."
        ],
    )

    report_evaluator = FakeReportEvaluator(
        [
            low_evaluation,
            low_evaluation,
            low_evaluation,
        ]
    )

    graph = build_research_graph(
        evaluation_service=FakeEvaluationService(),
        llm_provider=None,
        synthesizer=FakeSynthesizer(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=report_evaluator,
        max_evaluation_iterations=2,
    )

    result = await graph.ainvoke(
        build_initial_state()
    )

    assert report_evaluator.call_count == 2
    assert result["evaluation_iteration"] == 2
    assert result["report_evaluation"].score == 2
    assert result["report_evaluation"].hallucination_detected is True