import asyncio
import json
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import (
    ReportEvaluationRepository,
    ReportRepository,
    ResearchJobRepository,
)
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    ResearchReport,
    Source,
    SynthesizedClaim,
)
from app.workers.research_worker import ResearchWorker


def _make_fake_report() -> ResearchReport:
    src = Source(title="Test Source", url="https://example.com")
    evidence = Evidence(source=src, claim="Test claim", excerpt="Test excerpt")
    return ResearchReport(
        title="Test Report",
        executive_summary="Summary",
        key_findings=[SynthesizedClaim(claim="Test claim", citation_ids=[1])],
        detailed_analysis="Analysis",
        trade_offs=[],
        evidence=[evidence],
        limitations=[],
        conclusion="Conclusion",
        sources=[src],
    )


def _make_fake_evaluation() -> ReportEvaluation:
    return ReportEvaluation(
        grounded=True,
        citation_correct=True,
        hallucination_detected=False,
        score=5,
        reasoning="All good",
        unsupported_claims=[],
    )


@pytest.mark.asyncio
async def test_worker_persists_completion_and_publishes_progress():
    pool = await create_pool()
    store = RedisJobStore.from_env()
    research_id = str(uuid4())
    job_repository = ResearchJobRepository(pool)
    report_repository = ReportRepository(pool)
    report_eval_repository = ReportEvaluationRepository(pool)
    pubsub = None

    # Mock the production graph to avoid real LLM/Tavily calls
    fake_report = _make_fake_report()
    fake_eval = _make_fake_evaluation()
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "report": fake_report,
        "report_evaluation": fake_eval,
        "evaluation_iteration": 1,
    }

    try:
        job_id = await job_repository.create("Worker integration test")
        research_id = str(job_id)
        pubsub = await store.subscribe(research_id)
        # Allow subscription to propagate before worker starts publishing
        await asyncio.sleep(0.5)
        worker = ResearchWorker(
            store, job_repository, report_repository, report_eval_repository
        )

        async def collect_events():
            events = []
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                event = json.loads(message["data"])
                events.append(event)
                if event["status"] == "completed":
                    return events

        listener = asyncio.create_task(collect_events())
        with patch(
            "app.workers.research_worker.build_production_research_graph",
            return_value=mock_graph,
        ):
            await worker.process(research_id)
        events = await asyncio.wait_for(listener, timeout=2)

        job = await job_repository.get_by_id(job_id)
        assert job["status"] == "completed"
        progresses = [event["progress"] for event in events]
        assert "starting" in progresses
        assert "completed" in progresses
        # Verify report was persisted
        report = await report_repository.get_by_job_id(job_id)
        assert report is not None
        assert report["title"] == "Test Report"
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(f"research-events:{research_id}")
            await pubsub.aclose()
        await pool.execute("DELETE FROM report_evaluations WHERE job_id = $1", job_id)
        await pool.execute("DELETE FROM reports WHERE job_id = $1", job_id)
        await pool.execute(
            "DELETE FROM research_jobs WHERE id = $1",
            job_id,
        )
        await store.delete(research_id)
        await store.close()
        await pool.close()


@pytest.mark.asyncio
async def test_worker_marks_failed_when_graph_creation_fails():
    research_id = str(uuid4())
    job_store = AsyncMock()
    job_repository = AsyncMock()
    job_repository.get_by_id.return_value = {
        "question": "Test research question",
        "status": "pending",
    }
    report_repository = AsyncMock()
    evaluation_repository = AsyncMock()
    worker = ResearchWorker(
        job_store,
        job_repository,
        report_repository,
        evaluation_repository,
    )
    with patch(
        "app.workers.research_worker.build_production_research_graph",
        side_effect=ValueError("Missing required research credentials: GROQ_API_KEY, TAVILY_API_KEY"),
    ):
        with pytest.raises(ValueError, match="Missing required research credentials"):
            await worker.process(research_id)
    job_repository.update_status.assert_any_call(UUID(research_id), "failed")
    job_store.publish_event.assert_called()
    # ensure not marked completed
    assert not any(call.args[1] == "completed" for call in job_repository.update_status.call_args_list if len(call.args) > 1)


@pytest.mark.asyncio
async def test_worker_marks_failed_when_graph_raises():
    research_id = str(uuid4())
    job_store = AsyncMock()
    job_repository = AsyncMock()
    job_repository.get_by_id.return_value = {"question": "Test", "status": "pending"}
    report_repository = AsyncMock()
    evaluation_repository = AsyncMock()
    worker = ResearchWorker(job_store, job_repository, report_repository, evaluation_repository)
    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = RuntimeError("graph boom")
    with patch(
        "app.workers.research_worker.build_production_research_graph",
        return_value=mock_graph,
    ):
        with pytest.raises(RuntimeError, match="graph boom"):
            await worker.process(research_id)
    job_repository.update_status.assert_any_call(UUID(research_id), "failed")
    job_store.publish_event.assert_called()
    args, kwargs = job_store.publish_event.call_args
    assert args[0] == research_id
    assert args[1]["status"] == "failed"


@pytest.mark.asyncio
async def test_worker_marks_failed_when_report_persistence_fails():
    research_id = str(uuid4())
    job_store = AsyncMock()
    job_repository = AsyncMock()
    job_repository.get_by_id.return_value = {"question": "Test", "status": "pending"}
    report_repository = AsyncMock()
    report_repository.create_with_evaluation.side_effect = RuntimeError("db report fail")
    evaluation_repository = AsyncMock()
    worker = ResearchWorker(job_store, job_repository, report_repository, evaluation_repository)
    fake_report = _make_fake_report()
    fake_eval = _make_fake_evaluation()
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "report": fake_report,
        "report_evaluation": fake_eval,
        "evaluation_iteration": 1,
    }
    with patch(
        "app.workers.research_worker.build_production_research_graph",
        return_value=mock_graph,
    ):
        with pytest.raises(RuntimeError, match="db report fail"):
            await worker.process(research_id)
    job_repository.update_status.assert_any_call(UUID(research_id), "failed")
    report_repository.create_with_evaluation.assert_called_once()
    # ensure not marked completed
    completed_calls = [c for c in job_repository.update_status.call_args_list if c.args[1] == "completed"]
    assert not completed_calls


@pytest.mark.asyncio
async def test_worker_marks_failed_when_evaluation_persistence_fails():
    research_id = str(uuid4())
    job_store = AsyncMock()
    job_repository = AsyncMock()
    job_repository.get_by_id.return_value = {"question": "Test", "status": "pending"}
    report_repository = AsyncMock()
    report_repository.create_with_evaluation.side_effect = RuntimeError("eval db fail")
    evaluation_repository = AsyncMock()
    worker = ResearchWorker(job_store, job_repository, report_repository, evaluation_repository)
    fake_report = _make_fake_report()
    fake_eval = _make_fake_evaluation()
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {
        "report": fake_report,
        "report_evaluation": fake_eval,
        "evaluation_iteration": 2,
    }
    with patch(
        "app.workers.research_worker.build_production_research_graph",
        return_value=mock_graph,
    ):
        with pytest.raises(RuntimeError, match="eval db fail"):
            await worker.process(research_id)
    job_repository.update_status.assert_any_call(UUID(research_id), "failed")
    report_repository.create_with_evaluation.assert_called_once()
    # completed should not be called
    assert not any(c.args[1] == "completed" for c in job_repository.update_status.call_args_list)


@pytest.mark.asyncio
async def test_worker_marks_failed_when_report_missing():
    research_id = str(uuid4())
    job_store = AsyncMock()
    job_repository = AsyncMock()
    job_repository.get_by_id.return_value = {"question": "Test", "status": "pending"}
    report_repository = AsyncMock()
    evaluation_repository = AsyncMock()
    worker = ResearchWorker(job_store, job_repository, report_repository, evaluation_repository)
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"report": None, "report_evaluation": _make_fake_evaluation()}
    with patch(
        "app.workers.research_worker.build_production_research_graph",
        return_value=mock_graph,
    ):
        with pytest.raises(ValueError, match="no report"):
            await worker.process(research_id)
    job_repository.update_status.assert_any_call(UUID(research_id), "failed")
