import asyncio

import pytest

from app.db.postgres import create_pool
from app.db.repositories import ResearchJobRepository


@pytest.mark.asyncio
async def test_claim_next_pending_is_atomic():
    """Two workers concurrently claiming should not get the same job."""
    pool = await create_pool()
    try:
        repo1 = ResearchJobRepository(pool)
        repo2 = ResearchJobRepository(pool)

        # Clean up all pending jobs to ensure isolated test
        await pool.execute("DELETE FROM research_jobs WHERE status='pending'")

        # Create a single pending job
        job_id = await repo1.create(question="Duplicate claim test")

        # Try to claim concurrently from two workers - only one should get our job
        results = await asyncio.gather(
            repo1.claim_next_pending(),
            repo2.claim_next_pending(),
        )

        # Exactly one should have claimed our job, the other should be None (since only one pending)
        assert results.count(job_id) == 1, f"Expected exactly one claim of {job_id}, got {results}"
        assert results[0] != results[1] or (results[0] is None or results[1] is None)
        # One should be job_id, the other None
        assert (results[0] == job_id and results[1] is None) or (results[1] == job_id and results[0] is None)

        # Verify our job is now running
        job = await repo1.get_by_id(job_id)
        assert job["status"] == "running"

        # Cleanup
        await pool.execute("DELETE FROM report_evaluations WHERE job_id = $1", job_id)
        await pool.execute("DELETE FROM reports WHERE job_id = $1", job_id)
        await pool.execute("DELETE FROM research_jobs WHERE id = $1", job_id)
        # Also clean up any other jobs that might have been claimed
        for rid in results:
            if rid and rid != job_id:
                await pool.execute("DELETE FROM report_evaluations WHERE job_id = $1", rid)
                await pool.execute("DELETE FROM reports WHERE job_id = $1", rid)
                await pool.execute("DELETE FROM research_jobs WHERE id = $1", rid)
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_failed_job_retry_does_not_create_duplicate_reports():
    """A failed job retried should not leave duplicate reports."""
    pool = await create_pool()
    try:
        from app.db.repositories import ReportRepository, ReportEvaluationRepository
        from app.workers.research_worker import ResearchWorker
        from app.db.redis import RedisJobStore
        from unittest.mock import AsyncMock, patch
        from app.schemas.research import ResearchReport, ReportEvaluation, Source, Evidence, SynthesizedClaim
        from uuid import uuid4

        job_repo = ResearchJobRepository(pool)
        report_repo = ReportRepository(pool)
        eval_repo = ReportEvaluationRepository(pool)
        store = RedisJobStore.from_env()

        # Create a job
        job_id = await job_repo.create(question="Retry test")

        # First attempt: fail the graph
        mock_graph_fail = AsyncMock()
        mock_graph_fail.ainvoke.side_effect = RuntimeError("first fail")

        worker = ResearchWorker(store, job_repo, report_repo, eval_repo)
        with patch("app.workers.research_worker.build_production_research_graph", return_value=mock_graph_fail):
            with pytest.raises(RuntimeError):
                await worker.process(str(job_id))

        job = await job_repo.get_by_id(job_id)
        assert job["status"] == "failed"
        report = await report_repo.get_by_job_id(job_id)
        assert report is None  # No report on failure

        # Reset to pending for retry
        await pool.execute("UPDATE research_jobs SET status='pending' WHERE id=$1", job_id)

        # Second attempt: succeed
        def make_report():
            src = Source(title="Test", url="https://example.com")
            evidence = Evidence(source=src, claim="Test", excerpt="Test")
            return ResearchReport(
                title="Test Report",
                executive_summary="Summary",
                key_findings=[SynthesizedClaim(claim="Test", citation_ids=[1])],
                detailed_analysis="Analysis",
                trade_offs=[],
                evidence=[evidence],
                limitations=[],
                conclusion="Conclusion",
                sources=[src],
            )

        def make_eval():
            return ReportEvaluation(
                grounded=True, citation_correct=True, hallucination_detected=False, score=5, reasoning="ok", unsupported_claims=[]
            )

        mock_graph_success = AsyncMock()
        mock_graph_success.ainvoke.return_value = {
            "report": make_report(),
            "report_evaluation": make_eval(),
            "evaluation_iteration": 1,
        }

        with patch("app.workers.research_worker.build_production_research_graph", return_value=mock_graph_success):
            await worker.process(str(job_id))

        job = await job_repo.get_by_id(job_id)
        assert job["status"] == "completed"
        report = await report_repo.get_by_job_id(job_id)
        assert report is not None
        # Ensure only one report, not duplicate
        count = await pool.fetchval("SELECT COUNT(*) FROM reports WHERE job_id=$1", job_id)
        assert count == 1
        count_eval = await pool.fetchval("SELECT COUNT(*) FROM report_evaluations WHERE job_id=$1", job_id)
        assert count_eval == 1

        # Cleanup
        await pool.execute("DELETE FROM report_evaluations WHERE job_id=$1", job_id)
        await pool.execute("DELETE FROM reports WHERE job_id=$1", job_id)
        await pool.execute("DELETE FROM research_jobs WHERE id=$1", job_id)
        await store.close()
    finally:
        await pool.close()
