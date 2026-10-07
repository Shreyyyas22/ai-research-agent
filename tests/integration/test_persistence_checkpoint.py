from uuid import UUID

from app.db.postgres import create_pool
from app.db.repositories import (
    EvidenceRepository,
    ReportEvaluationRepository,
    ReportRepository,
    ResearchJobRepository,
    ResearchTaskRepository,
    SourceRepository,
)
from app.services.research_persistence import ResearchPersistenceService


async def main() -> None:
    pool = await create_pool()

    try:
        # ---------------------------------------------------------
        # Create repositories
        # ---------------------------------------------------------

        job_repository = ResearchJobRepository(pool)
        task_repository = ResearchTaskRepository(pool)
        source_repository = SourceRepository(pool)
        evidence_repository = EvidenceRepository(pool)
        report_repository = ReportRepository(pool)
        evaluation_repository = ReportEvaluationRepository(pool)

        # ---------------------------------------------------------
        # Create persistence service
        # ---------------------------------------------------------

        persistence_service = ResearchPersistenceService(
            job_repository=job_repository,
            task_repository=task_repository,
            source_repository=source_repository,
            evidence_repository=evidence_repository,
            report_repository=report_repository,
            evaluation_repository=evaluation_repository,
        )

        # ---------------------------------------------------------
        # 1. Persist research job
        # ---------------------------------------------------------

        job_id = await job_repository.create(
            question="What are the main differences between PostgreSQL and MongoDB?",
            status="running",
        )

        print(f"Created job: {job_id}")

        # ---------------------------------------------------------
        # 2. Persist research task
        # ---------------------------------------------------------

        task_id = await task_repository.create(
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

        # ---------------------------------------------------------
        # 3. Persist source
        # ---------------------------------------------------------

        source_id = await source_repository.create(
            job_id=job_id,
            title="PostgreSQL Documentation",
            url="https://www.postgresql.org/docs/",
        )

        print(f"Created source: {source_id}")

        # ---------------------------------------------------------
        # 4. Persist evidence
        # ---------------------------------------------------------

        evidence_id = await evidence_repository.create(
            source_id=source_id,
            claim="PostgreSQL is a relational database system.",
            excerpt=(
                "PostgreSQL is an open source object-relational "
                "database system."
            ),
        )

        print(f"Created evidence: {evidence_id}")

        # ---------------------------------------------------------
        # 5. Persist report
        # ---------------------------------------------------------

        report_id = await report_repository.create(
            job_id=job_id,
            title="PostgreSQL vs MongoDB",
            executive_summary=(
                "PostgreSQL and MongoDB use different data models."
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
                "This is a persistence checkpoint."
            ],
        )

        print(f"Created report: {report_id}")

        # ---------------------------------------------------------
        # 6. Persist evaluation
        # ---------------------------------------------------------

        evaluation_id = await evaluation_repository.create(
            job_id=job_id,
            report_id=report_id,
            iteration=1,
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning=(
                "The report is supported by persisted evidence."
            ),
            unsupported_claims=[],
        )

        print(f"Created evaluation: {evaluation_id}")

        # ---------------------------------------------------------
        # 7. Mark job completed
        # ---------------------------------------------------------

        await job_repository.update_status(
            job_id=job_id,
            status="completed",
            completed=True,
        )

        # ---------------------------------------------------------
        # 8. Reconstruct entire research job
        # ---------------------------------------------------------
        #
        # IMPORTANT:
        #
        # From this point onward, we only use the persistence service.
        #
        # No:
        # - LLM
        # - Planner
        # - Web Search
        # - Web Fetch
        # - RAG
        # - Research Graph
        #
        # is involved.
        # ---------------------------------------------------------

        result = await persistence_service.get_research_job(job_id)

        assert result is not None

        # ---------------------------------------------------------
        # Validate job
        # ---------------------------------------------------------

        job = result["job"]

        assert job["id"] == job_id
        assert job["question"] == (
            "What are the main differences between PostgreSQL and MongoDB?"
        )
        assert job["status"] == "completed"
        assert job["completed_at"] is not None

        # ---------------------------------------------------------
        # Validate tasks
        # ---------------------------------------------------------

        tasks = result["tasks"]

        assert len(tasks) == 1

        task = tasks[0]

        assert task["id"] == task_id
        assert task["job_id"] == job_id
        assert task["question"] == (
            "Compare PostgreSQL and MongoDB data models."
        )
        assert task["priority"] == 5
        assert task["status"] == "completed"

        # ---------------------------------------------------------
        # Validate sources
        # ---------------------------------------------------------

        sources = result["sources"]

        assert len(sources) == 1

        source = sources[0]

        assert source["id"] == source_id
        assert source["job_id"] == job_id
        assert source["title"] == "PostgreSQL Documentation"
        assert source["url"] == "https://www.postgresql.org/docs/"

        # ---------------------------------------------------------
        # Validate evidence
        # ---------------------------------------------------------

        evidence_by_source = result["evidence_by_source"]

        assert len(evidence_by_source) == 1
        assert source_id in evidence_by_source

        evidence = evidence_by_source[source_id]

        assert len(evidence) == 1

        assert evidence[0]["id"] == evidence_id
        assert evidence[0]["source_id"] == source_id
        assert evidence[0]["claim"] == (
            "PostgreSQL is a relational database system."
        )

        # ---------------------------------------------------------
        # Validate report
        # ---------------------------------------------------------

        report = result["report"]

        assert report is not None

        assert report["id"] == report_id
        assert report["job_id"] == job_id
        assert report["title"] == "PostgreSQL vs MongoDB"

        assert report["executive_summary"] == (
            "PostgreSQL and MongoDB use different data models."
        )

        assert report["conclusion"] == (
            "Both databases are useful for different workloads."
        )

        # ---------------------------------------------------------
        # Validate evaluations
        # ---------------------------------------------------------

        evaluations = result["evaluations"]

        assert len(evaluations) == 1

        evaluation = evaluations[0]

        assert evaluation["id"] == evaluation_id
        assert evaluation["job_id"] == job_id
        assert evaluation["report_id"] == report_id
        assert evaluation["iteration"] == 1
        assert evaluation["grounded"] is True
        assert evaluation["citation_correct"] is True
        assert evaluation["hallucination_detected"] is False
        assert evaluation["score"] == 5

        # ---------------------------------------------------------
        # Final Phase 17 checkpoint
        # ---------------------------------------------------------

        print()
        print("=" * 60)
        print("PHASE 17 PERSISTENCE CHECKPOINT PASSED")
        print("=" * 60)
        print()
        print(f"Research Job: {job_id}")
        print()
        print("Successfully reconstructed:")
        print("  ✓ Research Job")
        print("  ✓ Research Tasks")
        print("  ✓ Sources")
        print("  ✓ Evidence")
        print("  ✓ Report")
        print("  ✓ Report Evaluations")
        print()
        print("No LLM call required.")
        print("No web search required.")
        print("No RAG execution required.")
        print("No research recomputation required.")
        print()
        print("Complete research result loaded from PostgreSQL.")
        print("=" * 60)

    finally:
        await pool.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())