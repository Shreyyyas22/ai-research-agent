import asyncio

from app.tools.fake import FakeSearchTool


async def main() -> None:

    tool = FakeSearchTool()

    print("Name:")
    print(tool.name)

    print("\nDescription:")
    print(tool.description)

    result = await tool.execute(
        {
            "query": "PostgreSQL vs MongoDB"
        }
    )

    print("\nResult:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())