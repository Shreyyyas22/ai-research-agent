from __future__ import annotations

import asyncio
import os
from uuid import UUID

from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import ResearchJobRepository


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
        worker_id: str = "research-worker-1",
    ) -> None:
        self.job_store = job_store
        self.job_repository = job_repository
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

    async def process(
        self,
        research_id: str,
    ) -> None:
        """
        Process one research job.
        """

        job_uuid = UUID(research_id)

        try:
            # ---------------------------------------------------------
            # Job started
            # ---------------------------------------------------------

            await self.job_repository.update_status(
                job_uuid,
                "running",
            )

            await self.update_progress(
                research_id,
                "running",
                "starting",
            )

            print(
                f"[{self.worker_id}] "
                f"Started research job {research_id}"
            )

            # ---------------------------------------------------------
            # Planning
            # ---------------------------------------------------------

            await self.update_progress(
                research_id,
                "running",
                "planning",
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: planning"
            )

            await asyncio.sleep(1)

            # ---------------------------------------------------------
            # Researching
            # ---------------------------------------------------------

            await self.update_progress(
                research_id,
                "running",
                "researching",
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: researching"
            )

            await asyncio.sleep(2)

            # ---------------------------------------------------------
            # Synthesizing
            # ---------------------------------------------------------

            await self.update_progress(
                research_id,
                "running",
                "synthesizing",
            )

            print(
                f"[{self.worker_id}] "
                f"{research_id}: synthesizing"
            )

            await asyncio.sleep(1)

            # ---------------------------------------------------------
            # Completed
            # ---------------------------------------------------------

            await self.job_repository.update_status(
                job_uuid,
                "completed",
                completed=True,
            )

            await self.update_progress(
                research_id,
                "completed",
                "completed",
            )

            print(
                f"[{self.worker_id}] "
                f"Completed research job {research_id}"
            )

        except Exception as exc:
            # ---------------------------------------------------------
            # Failed
            # ---------------------------------------------------------

            await self.job_repository.update_status(
                job_uuid,
                "failed",
            )

            error_state = {
                "status": "failed",
                "progress": "failed",
                "worker_id": self.worker_id,
                "error": str(exc),
            }

            await self.job_store.set_state(
                research_id,
                error_state,
            )

            await self.job_store.publish_event(
                research_id,
                {
                    "type": "error",
                    **error_state,
                },
            )

            print(
                f"[{self.worker_id}] "
                f"Research job {research_id} failed: {exc}"
            )

            raise

    async def run_forever(
        self,
        poll_interval: float = 1.0,
    ) -> None:
        """Claim and process pending research jobs until stopped."""

        while True:
            research_id = await self.job_repository.claim_next_pending()

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

    job_repository = ResearchJobRepository(
        pool
    )

    worker = ResearchWorker(
        job_store=job_store,
        job_repository=job_repository,
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
