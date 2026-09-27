import asyncio

from app.tools.web_fetch import WebFetchTool

async def main() -> None:
    tool = WebFetchTool()

    print("Name:")
    print(tool.name)

    print("\nDescription:")
    print(tool.description)

    print("\nTesting safe URL:")

    result = await tool.execute(
        {
            "url": "https://example.com"
        }
    )

    print(result)

    print("\nTesting localhost:")

    result = await tool.execute(
        {
            "url": "http://127.0.0.1:8000"
        }
    )

    print(result)

    print("\nTesting cloud metadata IP:")

    result = await tool.execute(
        {
            "url": "http://169.254.169.254"
        }
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())