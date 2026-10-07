import json
import uuid
from typing import Any

import asyncpg


class ResearchJobRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        question: str,
        status: str = "pending",
    ) -> uuid.UUID:
        job_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO research_jobs (
                    id,
                    question,
                    status
                )
                VALUES ($1, $2, $3)
                """,
                job_id,
                question,
                status,
            )

        return job_id

    async def get_by_id(
        self,
        job_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT
                    id,
                    question,
                    status,
                    created_at,
                    completed_at
                FROM research_jobs
                WHERE id = $1
                """,
                job_id,
            )

        if row is None:
            return None

        return dict(row)

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        completed: bool = False,
    ) -> None:
        async with self.pool.acquire() as connection:
            if completed:
                await connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        status = $2,
                        completed_at = NOW()
                    WHERE id = $1
                    """,
                    job_id,
                    status,
                )
            else:
                await connection.execute(
                    """
                    UPDATE research_jobs
                    SET status = $2
                    WHERE id = $1
                    """,
                    job_id,
                    status,
                )


class ResearchTaskRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        job_id: uuid.UUID,
        question: str,
        search_queries: list[str],
        priority: int,
        status: str = "pending",
    ) -> uuid.UUID:
        task_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO research_tasks (
                    id,
                    job_id,
                    question,
                    search_queries,
                    priority,
                    status
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                """,
                task_id,
                job_id,
                question,
                json.dumps(search_queries),
                priority,
                status,
            )

        return task_id

    async def get_by_job_id(
        self,
        job_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    job_id,
                    question,
                    search_queries,
                    priority,
                    status,
                    created_at
                FROM research_tasks
                WHERE job_id = $1
                ORDER BY priority DESC, created_at ASC
                """,
                job_id,
            )

        return [dict(row) for row in rows]


class SourceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        job_id: uuid.UUID,
        title: str,
        url: str,
    ) -> uuid.UUID:
        source_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                INSERT INTO sources (
                    id,
                    job_id,
                    title,
                    url
                )
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (job_id, url)
                DO UPDATE SET
                    title = EXCLUDED.title
                RETURNING id
                """,
                source_id,
                job_id,
                title,
                url,
            )

        return row["id"]

    async def get_by_job_id(
        self,
        job_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    job_id,
                    title,
                    url,
                    created_at
                FROM sources
                WHERE job_id = $1
                ORDER BY created_at ASC
                """,
                job_id,
            )

        return [dict(row) for row in rows]


class EvidenceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        source_id: uuid.UUID,
        claim: str,
        excerpt: str,
    ) -> uuid.UUID:
        evidence_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO evidence (
                    id,
                    source_id,
                    claim,
                    excerpt
                )
                VALUES ($1, $2, $3, $4)
                """,
                evidence_id,
                source_id,
                claim,
                excerpt,
            )

        return evidence_id

    async def get_by_source_id(
        self,
        source_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    source_id,
                    claim,
                    excerpt,
                    created_at
                FROM evidence
                WHERE source_id = $1
                ORDER BY created_at ASC
                """,
                source_id,
            )

        return [dict(row) for row in rows]


class ReportRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        job_id: uuid.UUID,
        title: str,
        executive_summary: str,
        key_findings: list[dict[str, Any]],
        detailed_analysis: str,
        conclusion: str,
        trade_offs: list[str],
        limitations: list[str],
    ) -> uuid.UUID:
        report_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO reports (
                    id,
                    job_id,
                    title,
                    executive_summary,
                    key_findings,
                    detailed_analysis,
                    conclusion,
                    trade_offs,
                    limitations
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5::jsonb,
                    $6,
                    $7,
                    $8::jsonb,
                    $9::jsonb
                )
                """,
                report_id,
                job_id,
                title,
                executive_summary,
                json.dumps(key_findings),
                detailed_analysis,
                conclusion,
                json.dumps(trade_offs),
                json.dumps(limitations),
            )

        return report_id

    async def get_by_job_id(
        self,
        job_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        async with self.pool.acquire() as connection:
            row = await connection.fetchrow(
                """
                SELECT
                    id,
                    job_id,
                    title,
                    executive_summary,
                    key_findings,
                    detailed_analysis,
                    conclusion,
                    trade_offs,
                    limitations,
                    created_at
                FROM reports
                WHERE job_id = $1
                """,
                job_id,
            )

        if row is None:
            return None

        return dict(row)


class ReportEvaluationRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        job_id: uuid.UUID,
        report_id: uuid.UUID,
        iteration: int,
        grounded: bool,
        citation_correct: bool,
        hallucination_detected: bool,
        score: int,
        reasoning: str,
        unsupported_claims: list[str],
    ) -> uuid.UUID:
        evaluation_id = uuid.uuid4()

        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO report_evaluations (
                    id,
                    job_id,
                    report_id,
                    iteration,
                    grounded,
                    citation_correct,
                    hallucination_detected,
                    score,
                    reasoning,
                    unsupported_claims
                )
                VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    $5,
                    $6,
                    $7,
                    $8,
                    $9,
                    $10::jsonb
                )
                """,
                evaluation_id,
                job_id,
                report_id,
                iteration,
                grounded,
                citation_correct,
                hallucination_detected,
                score,
                reasoning,
                json.dumps(unsupported_claims),
            )

        return evaluation_id

    async def get_by_job_id(
        self,
        job_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    job_id,
                    report_id,
                    iteration,
                    grounded,
                    citation_correct,
                    hallucination_detected,
                    score,
                    reasoning,
                    unsupported_claims,
                    created_at
                FROM report_evaluations
                WHERE job_id = $1
                ORDER BY iteration ASC, created_at ASC
                """,
                job_id,
            )

        return [dict(row) for row in rows]