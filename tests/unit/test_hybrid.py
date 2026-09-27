import pytest

from app.retrieval.hybrid import ReciprocalRankFusion, HybridRetriever


def test_rrf_combines_ranked_lists() -> None:
    vector_results = [
        {"id": "A", "content": "Vector result A"},
        {"id": "B", "content": "Vector result B"},
        {"id": "C", "content": "Vector result C"},
    ]

    bm25_results = [
        {"id": "B", "content": "BM25 result B"},
        {"id": "C", "content": "BM25 result C"},
        {"id": "D", "content": "BM25 result D"},
    ]

    rrf = ReciprocalRankFusion(k=60)

    results = rrf.fuse(
        result_lists=[
            vector_results,
            bm25_results,
        ],
        top_k=4,
    )

    assert len(results) == 4

    result_ids = [result["id"] for result in results]

    assert set(result_ids) == {"A", "B", "C", "D"}

    # B appears at rank 2 in vector search
    # and rank 1 in BM25, so it should receive
    # strong combined evidence.
    assert results[0]["id"] == "B"


def test_rrf_score_is_added_to_results() -> None:
    results = [
        [
            {"id": "A", "content": "First result"},
        ],
    ]

    rrf = ReciprocalRankFusion(k=60)

    fused = rrf.fuse(results, top_k=1)

    assert fused[0]["id"] == "A"
    assert fused[0]["rrf_score"] == pytest.approx(1 / 61)


def test_rrf_handles_empty_result_lists() -> None:
    rrf = ReciprocalRankFusion()

    results = rrf.fuse([], top_k=5)

    assert results == []


def test_rrf_rejects_invalid_top_k() -> None:
    rrf = ReciprocalRankFusion()

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        rrf.fuse(
            [[{"id": "A", "content": "test"}]],
            top_k=0,
        )


def test_rrf_rejects_invalid_k() -> None:
    with pytest.raises(
        ValueError,
        match="k must be greater than zero",
    ):
        ReciprocalRankFusion(k=0)

class FakeVectorSearch:
    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
    ) -> list[dict]:
        return [
            {
                "id": "vector-1",
                "content": "Semantic vector result",
            },
            {
                "id": "shared",
                "content": "Result found by both systems",
            },
        ]


class FakeBM25:
    def search(
        self,
        query: str,
        top_k: int,
    ) -> list[dict]:
        return [
            {
                "id": "shared",
                "content": "Result found by both systems",
            },
            {
                "id": "bm25-1",
                "content": "Exact keyword result",
            },
        ]


@pytest.mark.asyncio
async def test_hybrid_retriever_combines_vector_and_bm25() -> None:
    retriever = HybridRetriever(
        vector_search=FakeVectorSearch(),
        bm25=FakeBM25(),
    )

    results = await retriever.search(
        query="HNSW vector search",
        query_embedding=[0.1, 0.2, 0.3],
        top_k=3,
    )

    result_ids = [result["id"] for result in results]

    assert "shared" in result_ids
    assert "vector-1" in result_ids
    assert "bm25-1" in result_ids


@pytest.mark.asyncio
async def test_hybrid_retriever_validates_query() -> None:
    retriever = HybridRetriever(
        vector_search=FakeVectorSearch(),
        bm25=FakeBM25(),
    )

    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        await retriever.search(
            query="",
            query_embedding=[0.1, 0.2],
        )


@pytest.mark.asyncio
async def test_hybrid_retriever_validates_embedding() -> None:
    retriever = HybridRetriever(
        vector_search=FakeVectorSearch(),
        bm25=FakeBM25(),
    )

    with pytest.raises(
        ValueError,
        match="Query embedding cannot be empty",
    ):
        await retriever.search(
            query="vector search",
            query_embedding=[],
        )