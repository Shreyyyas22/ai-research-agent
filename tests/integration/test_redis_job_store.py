import asyncio
from uuid import uuid4

from app.db.redis import RedisJobStore


async def main() -> None:
    store = RedisJobStore.from_env()

    research_id = str(uuid4())

    try:
        # Start with a queued job.
        await store.set_status(
            research_id,
            "queued",
        )

        status = await store.get_status(research_id)

        assert status == "queued"

        print(f"Initial status: {status}")

        # Simulate the worker starting the job.
        await store.set_status(
            research_id,
            "running",
        )

        status = await store.get_status(research_id)

        assert status == "running"

        print(f"Running status: {status}")

        # Store additional state.
        await store.set_state(
            research_id,
            {
                "progress": "researching",
                "worker_id": "worker-test-1",
            },
        )

        state = await store.get_state(research_id)

        assert state["status"] == "running"
        assert state["progress"] == "researching"
        assert state["worker_id"] == "worker-test-1"

        print(f"Stored state: {state}")

        # Complete the job.
        await store.set_status(
            research_id,
            "completed",
        )

        status = await store.get_status(research_id)

        assert status == "completed"

        print(f"Final status: {status}")

        print()
        print("RedisJobStore integration test PASSED.")

    finally:
        await store.delete(research_id)
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())