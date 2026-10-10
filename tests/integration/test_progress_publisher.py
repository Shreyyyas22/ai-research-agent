from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest

from app.db.redis import RedisJobStore
from app.services.progress_publisher import (
    ResearchProgressPublisher,
)


@pytest.mark.asyncio
async def test_progress_publisher():
    research_id = str(uuid4())

    publisher_store = RedisJobStore.from_env()
    subscriber_store = RedisJobStore.from_env()

    pubsub = None

    try:
        # Subscribe before publishing.
        pubsub = await subscriber_store.subscribe(
            research_id
        )

        publisher = ResearchProgressPublisher(
            research_id=research_id,
            job_store=publisher_store,
        )

        await publisher(
            "planning"
        )

        # Wait for the published event.
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            event = json.loads(
                message["data"]
            )

            assert event["type"] == "progress"
            assert event["status"] == "running"
            assert event["progress"] == "planning"

            break

        # Verify the latest state stored in Redis.
        state = await publisher_store.get_state(
            research_id
        )

        assert state["status"] == "running"
        assert state["progress"] == "planning"

        print(
            "Progress publisher integration test PASSED."
        )

    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(
                f"research-events:{research_id}"
            )

            await pubsub.aclose()

        await publisher_store.delete(
            research_id
        )

        await publisher_store.close()
        await subscriber_store.close()