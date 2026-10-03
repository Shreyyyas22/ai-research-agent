import pytest

from app.agents.graph import build_research_graph
from app.agents.state import ResearchState
from app.schemas.research import (
    Evidence,
    Source,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.citation_service import CitationService
from app.services.report_service import ReportService


class FakeEvaluationService:
    async def evaluate(self, question, evidence, llm_provider):
        class Evaluation:
            class Sufficiency:
                sufficient = True

            sufficiency = Sufficiency()
            conflicts = []

        return Evaluation()


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


@pytest.mark.asyncio
async def test_report_generation_checkpoint():
    source = Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )

    evidence = [
        Evidence(
            source=source,
            claim="PostgreSQL supports vector search.",
            excerpt="PostgreSQL can store and query vector data.",
        )
    ]

    graph = build_research_graph(
        evaluation_service=FakeEvaluationService(),
        llm_provider=None,
        synthesizer=FakeSynthesizer(),
        citation_service=CitationService(),
        report_service=ReportService(),
    )

    initial_state: ResearchState = {
        "question": "Does PostgreSQL support vector search?",
        "evidence": evidence,
        "sources": [source],
    }

    # The checkpoint focuses on the Phase 14 → Phase 15
    # synthesis → citation → report portion of the graph.
    initial_state["findings"] = SynthesisResult(
        claims=[
            SynthesizedClaim(
                claim="PostgreSQL supports vector search.",
                citation_ids=[1],
            )
        ]
    )

    result = await graph.ainvoke(initial_state)

    report = result["report"]

    assert report.title == (
        "Research Report: Does PostgreSQL support vector search?"
    )

    assert len(report.key_findings) == 1
    assert report.key_findings[0].claim == (
        "PostgreSQL supports vector search."
    )

    assert report.key_findings[0].citation_ids == [1]

    assert len(report.evidence) == 1
    assert len(report.sources) == 1

    assert result["citations"] == [1]