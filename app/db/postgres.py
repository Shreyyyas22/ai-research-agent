import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL is not set in .env")

    return database_url


async def create_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(
        get_database_url(),
        min_size=1,
        max_size=5,
    )