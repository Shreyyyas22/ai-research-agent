import pytest

from app.embeddings.fake import FakeEmbeddingProvider
from app.rag.chunking import chunk_text
from app.rag.ingestion import ingest_text
from app.rag.repository import RAGRepository


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.many = []

    async def execute(self, query, *args):
        self.executed.append((query, args))

    async def executemany(self, query, args):
        self.many.append((query, args))


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.connection)


def test_chunk_text_preserves_configured_overlap():
    assert chunk_text("abcdefghij", chunk_size=4, overlap=1) == [
        "abcd",
        "defg",
        "ghij",
    ]


@pytest.mark.parametrize("chunk_size, overlap", [(0, 0), (4, -1), (4, 4)])
def test_chunk_text_rejects_invalid_boundaries(chunk_size, overlap):
    with pytest.raises(ValueError):
        chunk_text("content", chunk_size=chunk_size, overlap=overlap)


def test_ingest_text_creates_linked_ordered_chunks():
    result = ingest_text(
        source="https://example.com/docs",
        title="Documentation",
        text="abcdefghij",
        chunk_size=4,
        overlap=1,
    )

    assert result["document"]["source"] == "https://example.com/docs"
    assert [chunk["chunk_index"] for chunk in result["chunks"]] == [0, 1, 2]
    assert all(
        chunk["document_id"] == result["document"]["id"]
        for chunk in result["chunks"]
    )


@pytest.mark.asyncio
async def test_fake_embeddings_are_stable_and_dimensioned():
    provider = FakeEmbeddingProvider(dimension=3)

    assert await provider.embed("PostgreSQL") == await provider.embed("PostgreSQL")
    assert len(await provider.embed("PostgreSQL")) == 3


@pytest.mark.asyncio
async def test_rag_repository_writes_document_and_vector_chunks():
    pool = FakePool()
    repository = RAGRepository(pool)
    document = {"id": "document-1", "source": "source", "title": "title"}
    chunks = [
        {
            "id": "chunk-1",
            "document_id": "document-1",
            "chunk_index": 0,
            "content": "content",
            "embedding": [0.1, 0.2],
        }
    ]

    await repository.insert_document(document)
    await repository.insert_chunks(chunks)

    assert "INSERT INTO documents" in pool.connection.executed[0][0]
    assert "::vector" in pool.connection.many[0][0]
    assert pool.connection.many[0][1][0][4] == "[0.1, 0.2]"
