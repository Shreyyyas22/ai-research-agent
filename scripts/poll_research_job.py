from __future__ import annotations

import asyncio
import sys

from app.db.redis import RedisJobStore


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python scripts/poll_research_job.py <research_id>"
        )

    research_id = sys.argv[1]

    store = RedisJobStore.from_env()

    try:
        state = await store.get_state(research_id)

        if not state:
            print(f"Research job not found: {research_id}")
            return

        print(f"Research ID: {research_id}")
        print(f"Status: {state.get('status')}")
        print(f"Progress: {state.get('progress')}")

        if state.get("worker_id"):
            print(f"Worker: {state['worker_id']}")

    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())