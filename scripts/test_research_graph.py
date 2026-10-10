
from __future__ import annotations

import asyncio
import json
import sys
from uuid import uuid4

from app.agents.graph import build_research_graph
from app.agents.planner import ResearchPlanner
from app.agents.researcher import Researcher
from app.agents.state import ResearchState
from app.db.redis import RedisJobStore
from app.schemas.research import (
    EvidenceExtraction,
    ResearchPlan,
    ResearchTask,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.citation_service import CitationService
from app.services.progress_publisher import ResearchProgressPublisher
from app.services.research_service import ResearchService
from app.services.report_service import ReportService
from app.tools.fake_provider import FakeSearchProvider
from app.tools.web_search import WebSearchTool


class FakePlanner:
    async def create_plan(self, question: str) -> ResearchPlan:
        return ResearchPlan(
            tasks=[
                ResearchTask(
                    question=question,
                    search_queries=["test query"],
                    priority=1,
                )
            ]
        )


class FakeEvaluationService:
    async def evaluate(
        self,
        question,
        evidence,
        llm_provider,
    ):
        class Evaluation:
            class Sufficiency:
                sufficient = True

            sufficiency = Sufficiency()
            conflicts = []

        return Evaluation()


class FakeWebFetchTool:
    async def execute(self, input):
        return {
            "success": True,
            "url": input["url"],
            "title": "Fake source",
            "content": (
                "PostgreSQL can store and query vector data."
            ),
            "error": None,
        }


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
                    "claim": (
                        "PostgreSQL supports vector search."
                    ),
                    "excerpt": (
                        "PostgreSQL can store and query vector data."
                    ),
                }
            ]
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
    async def evaluate(
        self,
        question,
        report,
        evidence,
        llm_provider,
    ):
        from app.schemas.research import ReportEvaluation

        return ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning=(
                "All report claims are supported "
                "by the supplied evidence."
            ),
            unsupported_claims=[],
        )


async def listen_for_progress(pubsub) -> list[dict]:
    """Listen for progress events until the graph completes."""
    events: list[dict] = []

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue

        event = json.loads(message["data"])
        events.append(event)

        print(f"[SSE EVENT] {event}")

        if event.get("progress") == "completed":
            break

    return events


async def main() -> None:
    research_id = (
        sys.argv[1]
        if len(sys.argv) > 1
        else str(uuid4())
    )

    print(f"Research ID: {research_id}")

    store = RedisJobStore.from_env()
    pubsub = None

    try:
        # Subscribe before running the graph.
        pubsub = await store.subscribe(research_id)

        progress_publisher = ResearchProgressPublisher(
            research_id=research_id,
            job_store=store,
        )

        # Use deterministic dependencies so this checkpoint
        # does not require a real search API or LLM API key.
        researcher = Researcher(
            tools={
                "web_search": WebSearchTool(
                    FakeSearchProvider()
                )
            }
        )

        research_service = ResearchService()

        graph = build_research_graph(
            researcher=researcher,
            research_service=research_service,
            planner=FakePlanner(),
            evaluation_service=FakeEvaluationService(),
            llm_provider=FakeEvidenceLLM(),
            synthesizer=FakeSynthesizer(),
            citation_service=CitationService(),
            report_service=ReportService(),
            report_evaluator=FakeReportEvaluator(),
            progress_callback=progress_publisher,
            web_fetch_tool=FakeWebFetchTool(),
        )

        initial_state: ResearchState = {
            "question": (
                "Does PostgreSQL support vector search?"
            ),
        }

        # Listen concurrently while the graph runs.
        listener_task = asyncio.create_task(
            listen_for_progress(pubsub)
        )

        print("\nStarting LangGraph...\n")

        try:
            result = await graph.ainvoke(initial_state)
            events = await listener_task
        except BaseException:
            listener_task.cancel()
            await asyncio.gather(
                listener_task,
                return_exceptions=True,
            )
            raise

        # Validate the final graph result.
        assert "report" in result
        assert len(result["evidence"]) == 2
        assert result["citations"] == [1]

        # Validate progress events.
        progress_values = [
            event["progress"]
            for event in events
        ]

        expected_progress = [
            "analyzing_query",
            "planning",
            "researching",
            "collecting_evidence",
            "evaluating_evidence",
            "synthesizing",
            "generating_citations",
            "building_report",
            "evaluating_report",
            "completed",
        ]

        assert progress_values == expected_progress, (
            f"Unexpected progress sequence: {progress_values}"
        )

        print("\nLangGraph progress integration PASSED.")
        print("\nProgress sequence:")

        for progress in progress_values:
            print(f"  ✓ {progress}")

    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(
                f"research-events:{research_id}"
            )
            await pubsub.aclose()

        await store.delete(research_id)
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())
