import asyncpg
import pytest

from app.db.postgres import create_pool
from app.db.repositories import ReportRepository, ResearchJobRepository


@pytest.mark.asyncio
async def test_report_and_evaluation_insert_roll_back_atomically():
    pool = await create_pool()

    try:
        job_repository = ResearchJobRepository(pool)
        report_repository = ReportRepository(pool)

        job_id = await job_repository.create(
            question="Test atomic report persistence rollback"
        )

        report_data = {
            "title": "Transaction rollback test",
            "executive_summary": "Test summary",
            "key_findings": [],
            "detailed_analysis": "Test analysis",
            "conclusion": "Test conclusion",
            "trade_offs": [],
            "limitations": [],
        }

        evaluation_data = {
            "grounded": None,  # Must violate the database NOT NULL constraint.
            "citation_correct": True,
            "hallucination_detected": False,
            "score": 3,
            "reasoning": "Rollback test",
            "unsupported_claims": [],
        }

        with pytest.raises(asyncpg.NotNullViolationError):
            await report_repository.create_with_evaluation(
                job_id=job_id,
                report_data=report_data,
                evaluation_data=evaluation_data,
                iteration=1,
            )

        # Verify the report INSERT was rolled back.
        # This query runs after the failed transaction has exited.
        async with pool.acquire() as conn:
            persisted_report = await conn.fetchrow(
                "SELECT id FROM reports WHERE job_id = $1",
                job_id,
            )

        assert persisted_report is None

    finally:
        await pool.close()
