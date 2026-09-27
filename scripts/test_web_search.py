import asyncio

from app.tools.fake_provider import FakeSearchProvider
from app.tools.web_search import WebSearchTool

async def main() -> None:
    provider = FakeSearchProvider()

    tool = WebSearchTool(provider)

    print("Name:")
    print(tool.name)

    print("\nDescription:")
    print(tool.description)

    result = await tool.execute(
        {
            "query": "PostgreSQL vs MongoDB"
        }
    )

    print("\nResult")

    print(result)

if __name__ == "__main__":
    asyncio.run(main())