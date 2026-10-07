from __future__ import annotations

from typing import Any
from uuid import UUID

from app.db.repositories import (
    EvidenceRepository,
    ReportEvaluationRepository,
    ReportRepository,
    ResearchJobRepository,
    ResearchTaskRepository,
    SourceRepository,
)


class ResearchPersistenceService:
    """
    Reconstructs a previously persisted research job.

    This service only reads from PostgreSQL.
    It does not perform research, call an LLM, or execute tools.
    """

    def __init__(
        self,
        job_repository: ResearchJobRepository,
        task_repository: ResearchTaskRepository,
        source_repository: SourceRepository,
        evidence_repository: EvidenceRepository,
        report_repository: ReportRepository,
        evaluation_repository: ReportEvaluationRepository,
    ) -> None:
        self.job_repository = job_repository
        self.task_repository = task_repository
        self.source_repository = source_repository
        self.evidence_repository = evidence_repository
        self.report_repository = report_repository
        self.evaluation_repository = evaluation_repository

    async def get_research_job(self, job_id: UUID) -> dict[str, Any] | None:
        """
        Fetch the complete persisted research job.

        No computation or external calls are performed.
        """

        job = await self.job_repository.get_by_id(job_id)

        if job is None:
            return None

        tasks = await self.task_repository.get_by_job_id(job_id)
        sources = await self.source_repository.get_by_job_id(job_id)
        report = await self.report_repository.get_by_job_id(job_id)
        evaluations = await self.evaluation_repository.get_by_job_id(job_id)

        evidence_by_source: dict[UUID, list[dict[str, Any]]] = {}

        for source in sources:
            source_id = source["id"]

            evidence_by_source[source_id] = (
                await self.evidence_repository.get_by_source_id(source_id)
            )

        return {
            "job": job,
            "tasks": tasks,
            "sources": sources,
            "evidence_by_source": evidence_by_source,
            "report": report,
            "evaluations": evaluations,
        }