from __future__ import annotations

import asyncio
import os
from uuid import UUID

from app.agents.production_factory import build_production_research_graph
from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import (
    ReportEvaluationRepository,
    ReportRepository,
    ResearchJobRepository,
)


class ResearchWorker:
    """
    Background worker responsible for processing research jobs.

    Redis:
        Stores live job status and publishes progress events.

    PostgreSQL:
        Stores the durable research job status.
    """

    def __init__(
        self,
        job_store: RedisJobStore,
        job_repository: ResearchJobRepository,
        report_repository: ReportRepository | None = None,
        report_evaluation_repository: ReportEvaluationRepository | None = None,
        worker_id: str = "research-worker-1",
    ) -> None:
        self.job_store = job_store
        self.job_repository = job_repository
        self.report_repository = report_repository
        self.report_evaluation_repository = report_evaluation_repository
        self.worker_id = worker_id

    async def update_progress(
        self,
        research_id: str,
        status: str,
        progress: str,
    ) -> None:
        """
        Update the latest Redis state and publish
        a live progress event.
        """

        state = {
            "status": status,
            "progress": progress,
            "worker_id": self.worker_id,
        }

        # Store the latest state in Redis.
        await self.job_store.set_state(
            research_id,
            state,
        )

        # Publish a live event through Redis Pub/Sub.
        await self.job_store.publish_event(
            research_id,
            {
                "type": "progress",
                **state,
            },
        )

        # Heartbeat: refresh lease for this job if it's still running
        try:
            job_uuid = UUID(research_id)
            await self.job_repository.heartbeat(job_uuid, self.worker_id)
        except Exception:
            # Heartbeat failures should not block progress updates
            pass

    async def process(
        self,
        research_id: str,
    ) -> None:
        from uuid import UUID

        job_uuid = UUID(str(research_id))

        try:
            job = await self.job_repository.get_by_id(job_uuid)
            if job is None:
                raise ValueError(f"Research job not found: {research_id}")
            question = job["question"]
            if not question or not question.strip():
                raise ValueError("Research job has an empty question")
            await self.job_repository.update_status(job_uuid, "running")
            await self.update_progress(research_id, "running", "starting")
            graph = build_production_research_graph(
                research_id=str(research_id),
                job_store=self.job_store,
            )
            result = await graph.ainvoke({"question": question})
            report = result.get("report")
            evaluation = result.get("report_evaluation")
            if report is None:
                raise ValueError("Research graph returned no report")
            if evaluation is None:
                raise ValueError("Research graph returned no report evaluation")
            if self.report_repository is not None:
                report_data = report.model_dump(mode="json")
                evaluation_data = evaluation.model_dump(mode="json")
                await self.report_repository.create_with_evaluation(
                    job_id=job_uuid,
                    report_data=report_data,
                    evaluation_data=evaluation_data,
                    iteration=result.get("evaluation_iteration", 1),
                )
            await self.job_repository.update_status(job_uuid, "completed", completed=True)
            await self.update_progress(research_id, "completed", "completed")
        except Exception as exc:
            try:
                await self.job_repository.update_status(job_uuid, "failed")
            except Exception as status_exc:
                print(f"Could not mark research job failed: {status_exc}")
            try:
                await self.job_store.publish_event(
                    str(research_id),
                    {
                        "type": "error",
                        "status": "failed",
                        "error": str(exc),
                    },
                )
            except Exception as redis_exc:
                print(f"Could not publish research failure: {redis_exc}")
            raise

    async def run_forever(
        self,
        poll_interval: float = 1.0,
    ) -> None:
        """Claim and process pending research jobs until stopped."""

        while True:
            research_id = await self.job_repository.claim_next_pending(
                worker_id=self.worker_id
            )

            if research_id is None:
                await asyncio.sleep(poll_interval)
                continue

            try:
                await self.process(str(research_id))
            except Exception as exc:
                # process() records the failed job and re-raises.
                # Keep the worker alive to handle subsequent jobs.
                print(
                    f"[{self.worker_id}] "
                    f"Continuing after job failure: {exc}"
                )
                await asyncio.sleep(poll_interval)


async def main() -> None:
    import sys

    if len(sys.argv) > 2:
        raise SystemExit(
            "Usage: uv run python -m "
            "app.workers.research_worker [research_id]"
        )

    research_id = sys.argv[1] if len(sys.argv) == 2 else None

    pool = await create_pool()
    job_store = RedisJobStore.from_env()

    job_repository = ResearchJobRepository(pool)
    report_repository = ReportRepository(pool)
    report_evaluation_repository = ReportEvaluationRepository(pool)

    worker = ResearchWorker(
        job_store=job_store,
        job_repository=job_repository,
        report_repository=report_repository,
        report_evaluation_repository=report_evaluation_repository,
        worker_id="research-worker-1",
    )

    try:
        if research_id is not None:
            await worker.process(research_id)
        else:
            poll_interval = float(
                os.getenv(
                    "WORKER_POLL_INTERVAL_SECONDS",
                    "1",
                )
            )
            await worker.run_forever(poll_interval)

    finally:
        await job_store.close()
        await pool.close()


if __name__ == "__main__":
    from app.observability.logging import configure_logging

    configure_logging()
    asyncio.run(main())
