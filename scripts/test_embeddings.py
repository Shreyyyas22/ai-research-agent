import asyncio

from app.embeddings.fake import FakeEmbeddingProvider

async def main() -> None:
    provider = FakeEmbeddingProvider(
        dimension=8,
    )

    text = (
        "PostgreSQL supports ACID transactions."
    )

    vector = await provider.embed(text)

    print("Dimesion:")
    print(provider.dimension)

    print("\nVector:")
    print(vector)

    print("\nVector length:")
    print(len(vector))

    vector_again = await provider.embed(text)

    print("\nDeterministic:")
    print(vector == vector_again)


if __name__ == "__main__":
    asyncio.run(main())