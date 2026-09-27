import pytest

from app.retrieval.reranker import PassthroughReranker


def test_passthrough_reranker_preserves_order() -> None:
    results = [
        {"id": "A", "rrf_score": 0.5},
        {"id": "B", "rrf_score": 0.4},
        {"id": "C", "rrf_score": 0.3},
    ]

    reranker = PassthroughReranker()

    output = reranker.rerank(
        query="test query",
        results=results,
        top_k=2,
    )

    assert [result["id"] for result in output] == ["A", "B"]


def test_passthrough_reranker_returns_all_when_top_k_is_large() -> None:
    results = [
        {"id": "A"},
        {"id": "B"},
    ]

    reranker = PassthroughReranker()

    output = reranker.rerank(
        query="test query",
        results=results,
        top_k=10,
    )

    assert output == results


def test_passthrough_reranker_rejects_empty_query() -> None:
    reranker = PassthroughReranker()

    with pytest.raises(
        ValueError,
        match="Query cannot be empty",
    ):
        reranker.rerank(
            query="",
            results=[],
        )


def test_passthrough_reranker_rejects_invalid_top_k() -> None:
    reranker = PassthroughReranker()

    with pytest.raises(
        ValueError,
        match="top_k must be greater than zero",
    ):
        reranker.rerank(
            query="test",
            results=[],
            top_k=0,
        )