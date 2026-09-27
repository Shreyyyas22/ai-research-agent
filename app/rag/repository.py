import json
from typing import Any

import asyncpg


class RAGRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def insert_document(
        self,
        document: dict[str, Any],
    ) -> None:
        async with self.pool.acquire() as connection:
            await connection.execute(
                """
                INSERT INTO documents (
                    id,
                    source,
                    title,
                    metadata
                )
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                document["id"],
                document["source"],
                document.get("title"),
                json.dumps(document.get("metadata", {})),
            )

    async def insert_chunks(
        self,
        chunks: list[dict[str, Any]],
            ) -> None:
        if not chunks:
            return

        async with self.pool.acquire() as connection:
            await connection.executemany(
                """
                INSERT INTO document_chunks (
                    id,
                    document_id,
                    chunk_index,
                    content,
                    embedding,
                    metadata
                )
                VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
                """,
                [
                    (
                        chunk["id"],
                        chunk["document_id"],
                        chunk["chunk_index"],
                        chunk["content"],
                        str(chunk["embedding"]),
                        json.dumps(chunk.get("metadata", {})),
                    )
                    for chunk in chunks
                ],
            )