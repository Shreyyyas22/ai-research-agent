import asyncio

from app.db.postgres import create_pool
from app.db.repositories import (
    EvidenceRepository,
    ReportEvaluationRepository,
    ReportRepository,
    ResearchJobRepository,
    ResearchTaskRepository,
    SourceRepository,
)


async def main() -> None:
    pool = await create_pool()

    try:
        job_repo = ResearchJobRepository(pool)
        task_repo = ResearchTaskRepository(pool)
        source_repo = SourceRepository(pool)
        evidence_repo = EvidenceRepository(pool)
        report_repo = ReportRepository(pool)
        evaluation_repo = ReportEvaluationRepository(pool)

        # 1. Create research job
        job_id = await job_repo.create(
            question="What are the main differences between PostgreSQL and MongoDB?",
            status="running",
        )

        print(f"Created job: {job_id}")

        # 2. Create research task
        task_id = await task_repo.create(
            job_id=job_id,
            question="Compare PostgreSQL and MongoDB data models.",
            search_queries=[
                "PostgreSQL data model",
                "MongoDB document model",
            ],
            priority=5,
            status="completed",
        )

        print(f"Created task: {task_id}")

        # 3. Create source
        source_id = await source_repo.create(
            job_id=job_id,
            title="PostgreSQL Documentation",
            url="https://www.postgresql.org/docs/",
        )

        print(f"Created source: {source_id}")

        # 4. Create evidence
        evidence_id = await evidence_repo.create(
            source_id=source_id,
            claim="PostgreSQL is a relational database system.",
            excerpt=(
                "PostgreSQL is an open source "
                "object-relational database system."
            ),
        )

        print(f"Created evidence: {evidence_id}")

        # 5. Create report
        report_id = await report_repo.create(
            job_id=job_id,
            title="PostgreSQL vs MongoDB",
            executive_summary=(
                "PostgreSQL and MongoDB use different data models "
                "and provide different approaches to data storage."
            ),
            key_findings=[
                {
                    "claim": "PostgreSQL uses a relational model.",
                    "citation_ids": [1],
                }
            ],
            detailed_analysis=(
                "PostgreSQL organizes data using relational tables, "
                "while MongoDB uses a document-oriented model."
            ),
            conclusion=(
                "Both databases are useful for different workloads."
            ),
            trade_offs=[
                "PostgreSQL provides strong relational capabilities.",
                "MongoDB provides a flexible document model.",
            ],
            limitations=[
                "This is a repository integration test.",
            ],
        )

        print(f"Created report: {report_id}")

        # 6. Create evaluation
        evaluation_id = await evaluation_repo.create(
            job_id=job_id,
            report_id=report_id,
            iteration=1,
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning=(
                "The report claims are supported by "
                "the supplied evidence."
            ),
            unsupported_claims=[],
        )

        print(f"Created evaluation: {evaluation_id}")

        # 7. Read everything back
        job = await job_repo.get_by_id(job_id)
        tasks = await task_repo.get_by_job_id(job_id)
        sources = await source_repo.get_by_job_id(job_id)
        evidence = await evidence_repo.get_by_source_id(source_id)
        report = await report_repo.get_by_job_id(job_id)
        evaluations = await evaluation_repo.get_by_job_id(job_id)

        print("\n--- Retrieved data ---")
        print(f"Job: {job}")
        print(f"Tasks: {tasks}")
        print(f"Sources: {sources}")
        print(f"Evidence: {evidence}")
        print(f"Report: {report}")
        print(f"Evaluations: {evaluations}")

        # 8. Basic assertions
        assert job is not None
        assert job["id"] == job_id

        assert len(tasks) == 1
        assert tasks[0]["id"] == task_id

        assert len(sources) == 1
        assert sources[0]["id"] == source_id

        assert len(evidence) == 1
        assert evidence[0]["id"] == evidence_id

        assert report is not None
        assert report["id"] == report_id

        assert len(evaluations) == 1
        assert evaluations[0]["id"] == evaluation_id

        # 9. Complete the job
        await job_repo.update_status(
            job_id=job_id,
            status="completed",
            completed=True,
        )

        updated_job = await job_repo.get_by_id(job_id)

        assert updated_job is not None
        assert updated_job["status"] == "completed"
        assert updated_job["completed_at"] is not None

        print("\nRepository integration test PASSED.")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())