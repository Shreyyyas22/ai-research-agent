import pytest

from app.agents.graph import build_research_graph
from app.agents.researcher import Researcher
from app.schemas.research import (
    EvidenceExtraction,
    ResearchPlan,
    ResearchTask,
    ReportEvaluation,
    SourceEvaluation,
    EvidenceSufficiency,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.citation_service import CitationService
from app.services.report_service import ReportService
from app.services.research_service import ResearchService
from app.tools.schemas import SearchResponse, SearchResult
from app.tools.web_search import WebSearchTool


class FakeSearchProvider:
    async def search(self, query):
        return SearchResponse(
            success=True,
            results=[
                SearchResult(
                    title="PostgreSQL Documentation",
                    url="https://example.com/postgresql",
                    snippet="PostgreSQL vector documentation",
                )
            ],
        )


class FakePlanner:
    async def create_plan(self, question):
        return ResearchPlan(
            tasks=[
                ResearchTask(
                    question=question,
                    search_queries=["PostgreSQL vector search"],
                    priority=1,
                )
            ]
        )


class FakeFetchTool:
    async def execute(self, input):
        return {
            "success": True,
            "content": "PostgreSQL can store and query vector data.",
        }


class FakeLLM:
    async def generate_structured(self, messages, response_model):
        assert response_model is EvidenceExtraction
        return EvidenceExtraction(
            evidence=[
                {
                    "claim": "PostgreSQL supports vector search.",
                    "excerpt": "PostgreSQL can store and query vector data.",
                }
            ]
        )


class FakeEvaluationService:
    async def evaluate(self, question, evidence, llm_provider):
        assert len(evidence) == 1
        return SourceEvaluation(
            sufficiency=EvidenceSufficiency(
                sufficient=True,
                reasoning="The evidence answers the question.",
            ),
            conflicts=[],
        )


class FakeSynthesizer:
    async def synthesize(self, question, evidence, conflicts, llm_provider):
        return SynthesisResult(
            claims=[
                SynthesizedClaim(
                    claim=evidence[0].claim,
                    citation_ids=[1],
                )
            ]
        )


class FakeReportEvaluator:
    async def evaluate(self, question, report, evidence, llm_provider):
        return ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning="The report is grounded in the evidence.",
        )


@pytest.mark.asyncio
async def test_research_question_produces_grounded_report():
    researcher = Researcher(
        tools={"web_search": WebSearchTool(FakeSearchProvider())}
    )
    graph = build_research_graph(
        researcher=researcher,
        research_service=ResearchService(),
        planner=FakePlanner(),
        evaluation_service=FakeEvaluationService(),
        llm_provider=FakeLLM(),
        synthesizer=FakeSynthesizer(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=FakeReportEvaluator(),
        web_fetch_tool=FakeFetchTool(),
    )

    result = await graph.ainvoke(
        {"question": "Does PostgreSQL support vector search?"}
    )

    assert result["research_sufficient"] is True
    assert result["citations"] == [1]
    assert result["report"].key_findings[0].claim == (
        "PostgreSQL supports vector search."
    )
    assert result["report"].evidence == result["evidence"]
