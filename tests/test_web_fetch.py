import httpx
import pytest

from app.tools.web_fetch import WebFetchTool


@pytest.mark.asyncio
async def test_fetch_html_success() -> None:

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        return httpx.Response(
            status_code=200,
            headers={
                "content-type": "text/html"
            },
            text="""
                <html>
                    <head>
                        <title>Test Page</title>
                        <script>
                            console.log("ignore me");
                        </script>
                    </head>

                    <body>
                        <h1>Hello World</h1>
                        <p>This is test content.</p>
                    </body>
                </html>
            """,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as client:

        tool = WebFetchTool(
            client=client,
        )

        result = await tool.execute(
            {
                "url": "https://example.com"
            }
        )

    assert result["success"] is True
    assert result["title"] == "Test Page"
    assert "Hello World" in result["content"]
    assert "This is test content." in result["content"]
    assert "console.log" not in result["content"]


@pytest.mark.asyncio
async def test_localhost_is_rejected() -> None:

    tool = WebFetchTool()

    result = await tool.execute(
        {
            "url": "http://127.0.0.1:8000"
        }
    )

    assert result["success"] is False
    assert "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_metadata_ip_is_rejected() -> None:

    tool = WebFetchTool()

    result = await tool.execute(
        {
            "url": "http://169.254.169.254"
        }
    )

    assert result["success"] is False
    assert "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_404_returns_controlled_error() -> None:

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        return httpx.Response(
            status_code=404,
            headers={
                "content-type": "text/html"
            },
            text="Not Found",
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as client:

        tool = WebFetchTool(
            client=client,
        )

        result = await tool.execute(
            {
                "url": "https://example.com/missing"
            }
        )

    assert result["success"] is False
    assert "404" in result["error"]


@pytest.mark.asyncio
async def test_unsupported_content_type() -> None:

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        return httpx.Response(
            status_code=200,
            headers={
                "content-type": "application/pdf"
            },
            content=b"fake pdf content",
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
    ) as client:

        tool = WebFetchTool(
            client=client,
        )

        result = await tool.execute(
            {
                "url": "https://example.com/file"
            }
        )

    assert result["success"] is False
    assert "content type" in result["error"].lower()


@pytest.mark.asyncio
async def test_redirects_are_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await WebFetchTool(client=client).execute(
            {"url": "https://example.com/redirect"}
        )

    assert result["success"] is False
    assert result["error"] == "Redirects are not allowed."


@pytest.mark.asyncio
async def test_non_object_tool_input_is_rejected() -> None:
    result = await WebFetchTool().execute([])

    assert result["success"] is False
    assert result["error"] == "Tool input must be an object."


@pytest.mark.asyncio
async def test_redirects_are_rejected() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/admin"},
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(transport=transport) as client:
        result = await WebFetchTool(client=client).execute(
            {"url": "https://example.com/redirect"}
        )

    assert result["success"] is False
    assert result["error"] == "Redirects are not allowed."


@pytest.mark.asyncio
async def test_non_object_tool_input_is_rejected() -> None:
    result = await WebFetchTool().execute([])

    assert result["success"] is False
    assert result["error"] == "Tool input must be an object."
