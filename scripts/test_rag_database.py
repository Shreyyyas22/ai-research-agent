import asyncio

from app.db.postgres import create_pool
from app.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)
from app.rag.ingestion import ingest_text
from app.rag.repository import RAGRepository


async def main() -> None:
    pool = await create_pool()

    try:
        repository = RAGRepository(pool)
        embedding_provider = SentenceTransformerEmbeddingProvider()

        result = ingest_text(
            source="manual-test",
            title="PostgreSQL RAG Test",
            text=(
                "PostgreSQL is a relational database. "
                "pgvector allows PostgreSQL to store and search vectors. "
                "This is useful for retrieval augmented generation."
            ),
            chunk_size=100,
            overlap=20,
        )

        chunks = result["chunks"]

        embeddings = await embedding_provider.embed_many(
            [chunk["content"] for chunk in chunks]
        )

        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding

        await repository.insert_document(
            result["document"]
        )

        await repository.insert_chunks(chunks)

        print("Document inserted successfully.")
        print(f"Chunks inserted: {len(chunks)}")
        print(f"Embedding dimension: {embedding_provider.dimension}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())