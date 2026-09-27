from app.tools.schemas import SearchResponse, SearchResult
from app.tools.search_provider import SearchProvider

class FakeSearchProvider(SearchProvider):

    async def search(
        self,
        query: str,
    ) -> SearchResponse:

        return SearchResponse(
            success=True,
            results=[
                SearchResult(
                    title="Fake PostgreSQL Result",
                    url="https://example.com/postgresql",
                    snippet=f"Fake search result for: {query}",
                ),
                SearchResult(
                    title="Fake MongoDB Result",
                    url="https://example.com/mongodb",
                    snippet=f"Another fake result for: {query}",
                ),
            ],
        )