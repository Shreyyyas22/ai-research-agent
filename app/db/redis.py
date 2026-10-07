from __future__ import annotations

import os
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()


def get_redis_url() -> str:
    """Return the Redis connection URL."""

    redis_url = os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    )

    return redis_url


class RedisJobStore:
    """
    Redis-backed store for research job state.

    Redis is used for short-lived/live job coordination.
    PostgreSQL remains the durable source of research data.
    """

    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "RedisJobStore":
        """Create a RedisJobStore using REDIS_URL."""

        client = redis.from_url(
            get_redis_url(),
            decode_responses=True,
        )

        return cls(client)

    def _key(self, research_id: str) -> str:
        """Build the Redis key for a research job."""

        return f"research:{research_id}"

    async def set_status(
        self,
        research_id: str,
        status: str,
    ) -> None:
        """Set the current status of a research job."""

        await self.client.hset(
            self._key(research_id),
            mapping={
                "status": status,
            },
        )

    async def get_status(
        self,
        research_id: str,
    ) -> str | None:
        """Get the current status of a research job."""

        status = await self.client.hget(
            self._key(research_id),
            "status",
        )

        return status

    async def set_state(
        self,
        research_id: str,
        state: dict[str, Any],
    ) -> None:
        """Store multiple job-state fields."""

        await self.client.hset(
            self._key(research_id),
            mapping={
                key: str(value)
                for key, value in state.items()
            },
        )

    async def get_state(
        self,
        research_id: str,
    ) -> dict[str, str]:
        """Return all stored state for a research job."""

        return await self.client.hgetall(
            self._key(research_id)
        )

    async def delete(
        self,
        research_id: str,
    ) -> None:
        """Delete a research job's Redis state."""

        await self.client.delete(
            self._key(research_id)
        )

    async def close(self) -> None:
        """Close the Redis connection."""

        await self.client.aclose()