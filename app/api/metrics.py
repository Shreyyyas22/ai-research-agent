from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.observability.metrics import generate_prometheus_text

router = APIRouter()


@router.get("/metrics")
async def metrics() -> PlainTextResponse:
    """Prometheus scrape endpoint — no secrets in exposition."""
    body = generate_prometheus_text()
    return PlainTextResponse(
        body,
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
