from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from app.db.postgres import create_pool
from app.db.repositories import ResearchJobRepository


async def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: uv run python scripts/check_research_job_db.py <research_id>"
        )

    research_id = UUID(sys.argv[1])

    pool = await create_pool()

    try:
        repository = ResearchJobRepository(pool)

        job = await repository.get_by_id(research_id)

        if job is None:
            print(f"Research job not found: {research_id}")
            return

        print(f"Research ID: {job['id']}")
        print(f"PostgreSQL status: {job['status']}")
        print(f"Created at: {job['created_at']}")
        print(f"Completed at: {job['completed_at']}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())