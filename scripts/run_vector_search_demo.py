import asyncio

from app.db.postgres import create_pool
from app.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)
from app.retrieval.vector_search import VectorSearch


async def main() -> None:
    pool = await create_pool()

    try:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_search = VectorSearch(pool)

        query = "How does PostgreSQL store and search vectors?"

        # Convert the user's query into a vector.
        query_embedding = await embedding_provider.embed(query)

        # Retrieve the most similar chunks.
        results = await vector_search.search(
            query_embedding=query_embedding,
            top_k=5,
        )

        print(f"Query: {query}")
        print(f"Results found: {len(results)}")
        print()

        for rank, result in enumerate(results, start=1):
            print(f"Rank: {rank}")
            print(f"Chunk index: {result['chunk_index']}")
            print(f"Distance: {result['distance']:.6f}")
            print(f"Content: {result['content']}")
            print("-" * 60)

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())