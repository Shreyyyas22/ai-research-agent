from __future__ import annotations

import asyncio
from uuid import UUID

from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import ResearchJobRepository


class ResearchWorker:
    """
    Background worker responsible for processing research jobs.

    Redis:
        Stores live job status and progress.

    PostgreSQL:
        Stores the durable research job status.
    """

    def __init__(
        self,
        job_store: RedisJobStore,
        job_repository: ResearchJobRepository,
        worker_id: str = "research-worker-1",
    ) -> None:
        self.job_store = job_store
        self.job_repository = job_repository
        self.worker_id = worker_id

    async def process(self, research_id: str) -> None:
        job_uuid = UUID(research_id)

        try:
            # Job started
            await self.job_repository.update_status(
                job_uuid,
                "running",
            )

            await self.job_store.set_state(
                research_id,
                {
                    "status": "running",
                    "progress": "starting",
                    "worker_id": self.worker_id,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"Started research job {research_id}"
            )

            # Planning
            await self.job_store.set_state(
                research_id,
                {
                    "status": "running",
                    "progress": "planning",
                    "worker_id": self.worker_id,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: planning"
            )

            await asyncio.sleep(1)

            # Researching
            await self.job_store.set_state(
                research_id,
                {
                    "status": "running",
                    "progress": "researching",
                    "worker_id": self.worker_id,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: researching"
            )

            await asyncio.sleep(2)

            # Synthesizing
            await self.job_store.set_state(
                research_id,
                {
                    "status": "running",
                    "progress": "synthesizing",
                    "worker_id": self.worker_id,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: synthesizing"
            )

            await asyncio.sleep(1)

            # Completed
            await self.job_repository.update_status(
                job_uuid,
                "completed",
                completed=True,
            )

            await self.job_store.set_state(
                research_id,
                {
                    "status": "completed",
                    "progress": "completed",
                    "worker_id": self.worker_id,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"Completed research job {research_id}"
            )

        except Exception as exc:
            await self.job_repository.update_status(
                job_uuid,
                "failed",
            )

            await self.job_store.set_state(
                research_id,
                {
                    "status": "failed",
                    "progress": "failed",
                    "worker_id": self.worker_id,
                    "error": str(exc),
                },
            )

            print(
                f"[{self.worker_id}] "
                f"Research job {research_id} failed: {exc}"
            )

            raise


async def main() -> None:
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python -m "
            "app.workers.research_worker <research_id>"
        )

    research_id = sys.argv[1]

    pool = await create_pool()
    job_store = RedisJobStore.from_env()

    job_repository = ResearchJobRepository(pool)

    worker = ResearchWorker(
        job_store=job_store,
        job_repository=job_repository,
        worker_id="research-worker-1",
    )

    try:
        await worker.process(research_id)

    finally:
        await job_store.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())