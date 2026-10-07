from __future__ import annotations

import asyncio

from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import ResearchJobRepository


async def main() -> None:
    pool = await create_pool()
    redis_store = RedisJobStore.from_env()

    try:
        # Create the durable research job in PostgreSQL
        job_repository = ResearchJobRepository(pool)

        research_id = await job_repository.create(
            question="Phase 18 background processing test",
            status="pending",
        )

        # Create the live job state in Redis
        await redis_store.set_state(
            str(research_id),
            {
                "status": "queued",
                "progress": "waiting_for_worker",
            },
        )

        print("Research job created.")
        print(f"research_id: {research_id}")
        print("PostgreSQL status: pending")
        print("Redis status: queued")

    finally:
        await redis_store.close()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())