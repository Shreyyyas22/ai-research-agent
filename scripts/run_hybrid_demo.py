import asyncio

from app.retrieval.bm25 import BM25
from app.retrieval.hybrid import ReciprocalRankFusion


DOCUMENTS = [
    {
        "id": "1",
        "content": (
            "Asynchronous tasks can be stopped before completion. "
            "Cancellation is commonly used to terminate long-running "
            "operations safely."
        ),
    },
    {
        "id": "2",
        "content": (
            "Python asyncio.CancelledError is raised when an asyncio "
            "task is cancelled."
        ),
    },
    {
        "id": "3",
        "content": (
            "Async programming allows applications to perform multiple "
            "operations without blocking the event loop."
        ),
    },
]


class FakeVectorSearch:
    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        # Simulated semantic ranking for demonstration.
        return [
            {
                **DOCUMENTS[2],
                "distance": 0.18,
            },
            {
                **DOCUMENTS[0],
                "distance": 0.24,
            },
            {
                **DOCUMENTS[1],
                "distance": 0.31,
            },
        ]


async def main() -> None:
    query = "How do I handle asyncio.CancelledError?"

    bm25 = BM25(DOCUMENTS)
    vector_search = FakeVectorSearch()

    bm25_results = bm25.search(
        query=query,
        top_k=3,
    )

    vector_results = await vector_search.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=3,
    )

    rrf = ReciprocalRankFusion()

    hybrid_results = rrf.fuse(
        result_lists=[
            vector_results,
            bm25_results,
        ],
        top_k=3,
    )

    print("=" * 70)
    print("QUERY")
    print(query)

    print("\nVECTOR RESULTS")
    for rank, result in enumerate(vector_results, start=1):
        print(
            f"{rank}. {result['id']} "
            f"(distance={result['distance']:.4f})"
        )

    print("\nBM25 RESULTS")
    for rank, result in enumerate(bm25_results, start=1):
        print(
            f"{rank}. {result['id']} "
            f"(score={result['score']:.4f})"
        )

    print("\nHYBRID / RRF RESULTS")
    for rank, result in enumerate(hybrid_results, start=1):
        print(
            f"{rank}. {result['id']} "
            f"(rrf={result['rrf_score']:.6f})"
        )

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())