import asyncio

from app.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddingProvider,
)


async def main() -> None:
    provider = SentenceTransformerEmbeddingProvider()

    print("Model loaded successfully.")

    print("\nDimension:")
    print(provider.dimension)

    text = "PostgreSQL supports ACID transactions."

    vector = await provider.embed(text)

    print("\nVector length:")
    print(len(vector))

    print("\nFirst 10 values:")
    print(vector[:10])

    print("\nDeterministic:")
    vector_again = await provider.embed(text)
    print(vector == vector_again)


if __name__ == "__main__":
    asyncio.run(main())