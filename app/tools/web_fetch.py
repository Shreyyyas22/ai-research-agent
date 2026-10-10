import logging
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.observability.logging import log_event
from app.tools.base import Tool
from app.tools.url_security import UnsafeURL, validate_url


class WebFetchTool(Tool):

    def __init__(
        self,
        timeout: float = 10.0,
        max_content_length: int = 1_000_000,
        client: httpx.AsyncClient | None = None,
    ) -> None:

        self.timeout = timeout
        self.max_content_length = max_content_length
        self.client = client

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch and extract readable text from a web page."

    async def execute(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        try:
            result = await self._fetch(input)
        except Exception:
            log_event(
                "tool_call_failed",
                level=logging.ERROR,
                logger_name="app.tools.web_fetch",
                tool="web_fetch",
                exc_info=True,
            )
            raise

        success = bool(result.get("success")) if isinstance(result, dict) else False
        log_event(
            "tool_call_completed" if success else "tool_call_failed",
            level=logging.INFO if success else logging.WARNING,
            logger_name="app.tools.web_fetch",
            tool="web_fetch",
            success=success,
            duration_seconds=round(time.perf_counter() - started_at, 6),
            url=result.get("url") if isinstance(result, dict) else None,
        )
        return result

    async def _fetch(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:

        if not isinstance(input, dict):
            return {
                "success": False,
                "url": "",
                "title": None,
                "content": "",
                "error": "Tool input must be an object.",
            }

        url = input.get("url")

        if not isinstance(url, str) or not url.strip():
            return {
                "success": False,
                "url": "",
                "title": None,
                "content": "",
                "error": "URL must be a non-empty string.",
            }

        try:
            validate_url(url)

        except UnsafeURL as exc:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": str(exc),
            }

        try:

            if self.client is not None:

                response = await self.client.get(url)

            else:

                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=False,
                ) as client:

                    response = await client.get(
                        url,
                        headers={
                            "User-Agent": (
                                "AIResearchAgent/0.1"
                            )
                        },
                    )

        except httpx.TimeoutException:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": "Request timed out.",
            }

        except httpx.HTTPError as exc:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": f"HTTP request failed: {exc}",
            }

        if response.status_code == 404:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": "HTTP 404: page not found.",
            }

        if 300 <= response.status_code < 400:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": "Redirects are not allowed.",
            }

        if response.status_code >= 400:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": (
                    f"HTTP {response.status_code}: "
                    "request failed."
                ),
            }

        content_type = response.headers.get(
            "content-type",
            "",
        ).lower()

        if "text/html" not in content_type:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": (
                    f"Unsupported content type: "
                    f"{content_type}"
                ),
            }

        if len(response.content) > self.max_content_length:
            return {
                "success": False,
                "url": url,
                "title": None,
                "content": "",
                "error": "Response body is too large.",
            }

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for element in soup(
            ["script", "style", "noscript"]
        ):
            element.decompose()

        title = (
            soup.title.get_text(strip=True)
            if soup.title
            else None
        )

        content = soup.get_text(
            separator=" ",
            strip=True,
        )

        return {
            "success": True,
            "url": url,
            "title": title,
            "content": content,
            "error": None,
        }
