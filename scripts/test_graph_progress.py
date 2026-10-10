from __future__ import annotations

import asyncio
import json
import sys

from app.db.redis import RedisJobStore
from app.services.progress_publisher import (
    ResearchProgressPublisher,
)


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python "
            "scripts/test_graph_progress.py <research_id>"
        )

    research_id = sys.argv[1]

    store = RedisJobStore.from_env()

    try:
        publisher = ResearchProgressPublisher(
            research_id=research_id,
            job_store=store,
        )

        print(
            f"Graph progress publisher ready for: "
            f"{research_id}"
        )

        await publisher("analyzing_query")
        await publisher("planning")
        await publisher("researching")
        await publisher("collecting_evidence")
        await publisher("evaluating_evidence")
        await publisher("synthesizing")
        await publisher("generating_citations")
        await publisher("building_report")
        await publisher("evaluating_report")
        await publisher("completed")

        print(
            "Graph progress events published successfully."
        )

    finally:
        await store.close()


if __name__ == "__main__":
    asyncio.run(main())