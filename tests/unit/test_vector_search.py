import pytest

from app.retrieval.vector_search import VectorSearch


class FakeConnection:
    def __init__(self) -> None:
        self.received_query = None
        self.received_args = None

    async def fetch(self, query: str, *args):
        self.received_query = query
        self.received_args = args

        return [
            {
                "id": "11111111-1111-1111-1111-111111111111",
                "document_id": "22222222-2222-2222-2222-222222222222",
                "chunk_index": 0,
                "content": "PostgreSQL stores vectors using pgvector.",
                "metadata": {},
                "distance": 0.12,
            },
            {
                "id": "33333333-3333-3333-3333-333333333333",
                "document_id": "22222222-2222-2222-2222-222222222222",
                "chunk_index": 1,
                "content": "Vector similarity can be used for semantic retrieval.",
                "metadata": {},
                "distance": 0.31,
            },
        ]


class FakeAcquire:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.connection)


@pytest.mark.asyncio
async def test_vector_search_returns_results() -> None:
    pool = FakePool()
    search = VectorSearch(pool)

    results = await search.search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["chunk_index"] == 0
    assert results[0]["distance"] == 0.12
    assert results[1]["chunk_index"] == 1


@pytest.mark.asyncio
async def test_vector_search_passes_query_embedding_and_top_k() -> None:
    pool = FakePool()
    search = VectorSearch(pool)

    query_embedding = [0.1, 0.2, 0.3]

    await search.search(
        query_embedding=query_embedding,
        top_k=3,
    )

    assert pool.connection.received_args == ("[0.1, 0.2, 0.3]", 3)
    assert "<=>" in pool.connection.received_query
    assert "ORDER BY embedding <=> $1::vector" in pool.connection.received_query
    assert "LIMIT $2" in pool.connection.received_query


@pytest.mark.asyncio
async def test_vector_search_rejects_empty_embedding() -> None:
    pool = FakePool()
    search = VectorSearch(pool)

    with pytest.raises(ValueError, match="Query embedding cannot be empty"):
        await search.search([], top_k=5)


@pytest.mark.asyncio
async def test_vector_search_rejects_invalid_top_k() -> None:
    pool = FakePool()
    search = VectorSearch(pool)

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        await search.search([0.1, 0.2, 0.3], top_k=0)