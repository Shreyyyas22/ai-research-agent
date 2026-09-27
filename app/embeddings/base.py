from abc import ABC, abstractmethod

class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        ...

    @abstractmethod
    async def embed(
        self,
        text: str,
    ) -> list[list[float]]:
        return [
            await self.embed(text)
            for text in texts
        ]