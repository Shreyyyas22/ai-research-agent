from __future__ import annotations

import asyncio
import json
import sys

from app.db.redis import RedisJobStore


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python "
            "scripts/test_redis_pubsub.py <research_id>"
        )

    research_id = sys.argv[1]

    publisher = RedisJobStore.from_env()
    subscriber = RedisJobStore.from_env()

    pubsub = None

    try:
        pubsub = await subscriber.subscribe(
            research_id
        )

        print(
            f"Listening for events for research job: "
            f"{research_id}"
        )

        print(
            "Waiting for worker events..."
        )

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            raw_data = message["data"]

            try:
                event = json.loads(raw_data)

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Invalid JSON received: {raw_data}"
                ) from exc

            print(
                f"Received event: {event}"
            )

            if event.get("status") in {
                "completed",
                "failed",
            }:
                break

    finally:
        if pubsub is not None:
            await pubsub.unsubscribe(
                f"research-events:{research_id}"
            )

            await pubsub.aclose()

        await publisher.close()
        await subscriber.close()


if __name__ == "__main__":
    asyncio.run(main())