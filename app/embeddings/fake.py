import hashlib

from app.embeddings.base import EmbeddingProvider

class FakeEmbeddingProvider(EmbeddingProvider):

    def __init__(
        self,
        dimension: int = 8,
    ) -> None:

        self._dimension = dimension
    
    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(
        self,
        text: str,
    ) -> list[float]:

        digest = hashlib.sha256(
            text.encode("utf-8")
        ).digest()

        values: list[float] = []

        for index in range(self.dimension):
            byte = digest[index % len(digest)]

            value = (
                (byte / 255.0) * 2.0
            ) - 1.0

            values.append(value)

        return values