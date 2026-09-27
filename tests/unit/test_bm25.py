import pytest

from app.retrieval.bm25 import BM25


DOCUMENTS = [
    {
        "id": "1",
        "content": (
            "PostgreSQL stores vector embeddings using pgvector."
        ),
    },
    {
        "id": "2",
        "content": (
            "BM25 performs lexical keyword retrieval."
        ),
    },
    {
        "id": "3",
        "content": (
            "HNSW provides approximate nearest neighbor vector search."
        ),
    },
]


def test_bm25_returns_keyword_relevant_document() -> None:
    bm25 = BM25(DOCUMENTS)

    results = bm25.search(
        "pgvector embeddings",
        top_k=3,
    )

    assert results[0]["id"] == "1"
    assert results[0]["score"] > 0


def test_bm25_prefers_exact_technical_term() -> None:
    bm25 = BM25(DOCUMENTS)

    results = bm25.search(
        "HNSW",
        top_k=3,
    )

    assert results[0]["id"] == "3"


def test_bm25_returns_top_k_results() -> None:
    bm25 = BM25(DOCUMENTS)

    results = bm25.search(
        "vector search",
        top_k=2,
    )

    assert len(results) == 2


def test_bm25_rejects_empty_query() -> None:
    bm25 = BM25(DOCUMENTS)

    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        bm25.search("")


def test_bm25_rejects_invalid_top_k() -> None:
    bm25 = BM25(DOCUMENTS)

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        bm25.search("vector", top_k=0)