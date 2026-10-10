from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.db.redis import RedisJobStore


router = APIRouter()


async def event_stream(
    research_id: str,
) -> AsyncGenerator[str, None]:
    """
    Stream research progress events as Server-Sent Events.
    """

    store = RedisJobStore.from_env()
    pubsub = None

    try:
        pubsub = await store.subscribe(
            research_id
        )

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            raw_data = message["data"]

            try:
                data = json.loads(raw_data)

            except json.JSONDecodeError:
                data = {
                    "type": "error",
                    "message": "Invalid event payload",
                }

            event_type = data.get(
                "type",
                "progress",
            )

            yield (
                f"event: {event_type}\n"
                f"data: {json.dumps(data)}\n\n"
            )

            if data.get("status") in {
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

        await store.close()


@router.get(
    "/research/{research_id}/stream"
)
async def stream_research_progress(
    research_id: str,
) -> StreamingResponse:
    """
    Stream live research progress for a research job.
    """

    return StreamingResponse(
        event_stream(research_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )