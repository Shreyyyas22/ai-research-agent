from app.rag.chunking import chunk_text
from app.rag.ingestion import ingest_text

def main() -> None:
    text = (
        "PostgreSQL is an open-source relational database system. "
        "It supports ACID transactions and complex queries. "
        "pgvector adds vector similarity search capabilities. "
        "This makes PostgreSQL useful for building RAG systems."
    )

    print("===== CHUNKING ========")

    chunks = chunk_text(
        text,
        chunk_size=100,
        overlap=20,
    )

    for index, chunk in enumerate(chunks):
        print(f"\nChunk {index}:")
        print(chunk)

    print("\n==== INGESTION =====")

    result = ingest_text(
        source="https://example.com/postgresql",
        title="PostgreSQL Introduction",
        text=text,
        chunk_size=100,
        overlap=20,
    )

    print("\nDocument:")
    print(result["document"])

    print("\nNumber of chunks:")
    print(len(result["chunks"]))

    print("\nFirst chunk:")
    print(result["chunks"][0])


if __name__ == "__main__":
    main()