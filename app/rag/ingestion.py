from uuid import uuid4

from app.rag.chunking import chunk_text

def ingest_text(
    source: str,
    title: str,
    text: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> dict:
    document_id = uuid4()

    chunks = chunk_text(
        text=text,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    return {
        "document": {
            "id": str(document_id),
            "source": source,
            "title": title,
        },
        "chunks": [
            {
                "id": str(uuid4()),
                "document_id": str(document_id),
                "chunk_index": index,
                "content": content,
            }
            for index, content in enumerate(chunks)
        ],
    }