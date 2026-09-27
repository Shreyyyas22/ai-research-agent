from typing import Any

import asyncpg


class VectorSearch:
    """Semantic vector search over stored document chunks."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        vector_literal = str(query_embedding)

        async with self.pool.acquire() as connection:
            rows = await connection.fetch(
                """
                SELECT
                    id,
                    document_id,
                    chunk_index,
                    content,
                    metadata,
                    embedding <=> $1::vector AS distance
                FROM document_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT $2
                """,
                vector_literal,
                top_k,
            )

        return [
            {
                "id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "metadata": row["metadata"],
                "distance": float(row["distance"]),
            }
            for row in rows
        ]