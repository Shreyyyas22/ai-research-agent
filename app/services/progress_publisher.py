from __future__ import annotations

from typing import Any

from app.db.redis import RedisJobStore


class ResearchProgressPublisher:
    """
    Publishes safe research progress events to Redis.
    """

    def __init__(
        self,
        research_id: str,
        job_store: RedisJobStore,
    ) -> None:
        self.research_id = research_id
        self.job_store = job_store

    async def __call__(
        self,
        progress: str,
    ) -> None:
        event: dict[str, Any] = {
            "type": "progress",
            "status": "running",
            "progress": progress,
        }

        await self.job_store.set_state(
            self.research_id,
            event,
        )

        await self.job_store.publish_event(
            self.research_id,
            event,
        )