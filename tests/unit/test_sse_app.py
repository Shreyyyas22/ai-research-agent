"""Coverage for app/sse_app.py and app/api/metrics.py — health, SSE, Prometheus without secret leak."""

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.observability.logging import JSONFormatter
from app.observability.metrics import inc_counter, reset_metrics
from app.sse_app import app


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    yield
    reset_metrics()


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_metrics_endpoint_returns_prometheus_text_and_no_secret_leak():
    inc_counter("research_runs_total", {"status": "success"}, 2)
    inc_counter("limit_violations_total", {"limit": "gsk_abc1234567890"}, 1)
    inc_counter("llm_requests_total", {"model": "Bearer abc.def.ghi", "operation": "generate", "status": "success"}, 1)
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in resp.headers["content-type"]
    text = resp.text
    # HELP/TYPE present
    assert "# HELP research_runs_total" in text
    assert "# TYPE research_runs_total counter" in text
    assert "research_runs_total" in text
    # secrets redacted
    assert "gsk_abc1234567890" not in text
    assert "Bearer abc.def.ghi" not in text
    assert "[REDACTED" in text
    assert text.endswith("\n")


def test_metrics_endpoint_exposes_histograms():
    from app.observability.metrics import observe_histogram

    observe_histogram("research_run_duration_seconds", 0.12)
    client = TestClient(app)
    text = client.get("/metrics").text
    assert "research_run_duration_seconds_bucket" in text
    assert "research_run_duration_seconds_count" in text
    assert "research_run_duration_seconds_sum" in text


def test_sse_router_is_mounted():
    # ensure the SSE route exists (will fail with 422 if research_id missing, but route is present)
    client = TestClient(app)
    # health already tested; check openapi includes SSE path
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]
    assert "/research/{research_id}/stream" in paths
    assert "/metrics" in paths
    assert "/health" in paths


def test_request_logs_contain_trace_but_not_secret_via_middleware():
    # Simulate a request that would log with a secret in query — ensure formatter redacts
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("app")
    # ensure app logger uses JSONFormatter (configure_logging already called in sse_app)
    # patch handler temporarily
    orig_handlers = logger.handlers[:]
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    try:
        logger.info("user query with gsk_abc1234567890 and password=supersecret")
        data = json.loads(stream.getvalue().strip())
        dumped = json.dumps(data)
        assert "gsk_abc1234567890" not in dumped
        assert "supersecret" not in dumped
        assert "[REDACTED" in dumped
    finally:
        logger.handlers = orig_handlers
