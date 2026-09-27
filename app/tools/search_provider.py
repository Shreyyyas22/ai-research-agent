from abc import ABC, abstractmethod

from app.tools.schemas import SearchResponse

class SearchProvider(ABC):
    @abstractmethod
    async def search(
        self,
        query: str,
    ) -> SearchResponse:
        ...