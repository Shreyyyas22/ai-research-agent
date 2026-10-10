import asyncio
import json
from uuid import uuid4

import pytest

from app.db.postgres import create_pool
from app.db.redis import RedisJobStore
from app.db.repositories import ResearchJobRepository
from app.workers.research_worker import ResearchWorker


@pytest.mark.asyncio
async def test_worker_persists_completion_and_publishes_progress():
    pool = await create_pool()
    store = RedisJobStore.from_env()
    research_id = str(uuid4())
    job_repository = ResearchJobRepository(pool)
    pubsub = None

    try:
        job_id = await job_repository.create("Worker integration test")
        research_id = str(job_id)
        pubsub = await store.subscribe(research_id)
        worker = ResearchWorker(store, job_repository)

        async def collect_events():
            events = []
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                event = json.loads(message["data"])
                events.append(event)
                if event["status"] == "completed":
                    return events

        listener = asyncio.create_task(collect_events())
        await worker.process(research_id)
        events = await asyncio.wait_for(listener, timeout=2)

        job = await job_repository.get_by_id(job_id)
        assert job["status"] == "completed"
        assert [event["progress"] for event in events] == [
            "starting",
            "planning",
            "researching",
            "synthesizing",
            "completed",
        ]
    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(f"research-events:{research_id}")
            await pubsub.aclose()
        await pool.execute(
            "DELETE FROM research_jobs WHERE id = $1",
            job_id,
        )
        await store.delete(research_id)
        await store.close()
        await pool.close()
