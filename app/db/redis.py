from __future__ import annotations

import json
import os
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()


def get_redis_url() -> str:
    return os.getenv(
        "REDIS_URL",
        "redis://localhost:6379/0",
    )


class RedisJobStore:
    def __init__(self, client: redis.Redis) -> None:
        self.client = client

    @classmethod
    def from_env(cls) -> "RedisJobStore":
        client = redis.from_url(
            get_redis_url(),
            decode_responses=True,
        )

        return cls(client)

    def _key(self, research_id: str) -> str:
        return f"research:{research_id}"

    def _channel(self, research_id: str) -> str:
        return f"research-events:{research_id}"

    async def set_status(
        self,
        research_id: str,
        status: str,
    ) -> None:
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
        return await self.client.hget(
            self._key(research_id),
            "status",
        )

    async def set_state(
        self,
        research_id: str,
        state: dict[str, Any],
    ) -> None:
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
        return await self.client.hgetall(
            self._key(research_id)
        )

    async def publish_event(
        self,
        research_id: str,
        event: dict[str, Any],
    ) -> None:
        await self.client.publish(
            self._channel(research_id),
            json.dumps(event),
        )

    async def subscribe(
        self,
        research_id: str,
    ):
        pubsub = self.client.pubsub()

        await pubsub.subscribe(
            self._channel(research_id)
        )

        return pubsub

    async def delete(
        self,
        research_id: str,
    ) -> None:
        await self.client.delete(
            self._key(research_id)
        )

    async def close(self) -> None:
        await self.client.aclose()