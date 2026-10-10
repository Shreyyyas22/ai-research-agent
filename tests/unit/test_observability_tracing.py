"""Coverage for app/observability/tracing — spans for graph, LLM, tool with failure paths."""

import io
import json
import logging

import pytest

from app.observability.logging import JSONFormatter
from app.observability.metrics import reset_metrics, generate_prometheus_text
from app.observability.tracing import (
    create_span,
    create_span_id,
    create_trace_id,
    trace_llm_request,
    trace_tool_call,
    trace_node,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    yield
    reset_metrics()


def _capture_logger(name: str):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger(name)
    orig_handlers = logger.handlers[:]
    orig_level = logger.level
    orig_propagate = logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return stream, logger, orig_handlers, orig_level, orig_propagate


def _restore_logger(logger, orig_handlers, orig_level, orig_propagate):
    logger.handlers = orig_handlers
    logger.setLevel(orig_level)
    logger.propagate = orig_propagate


def test_create_trace_and_span_ids_format():
    tid = create_trace_id()
    sid = create_span_id()
    assert len(tid) == 32  # uuid hex
    assert len(sid) == 16
    assert tid.isalnum()
    assert sid.isalnum()


def test_create_span_logs_started_and_completed_and_records_metrics():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        with create_span("my_span", {"foo": "bar"}) as span:
            assert "trace_id" in span and "span_id" in span
            assert span["name"] == "my_span"
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_span_started" for l in logs)
        assert any(l["message"] == "trace_span_completed" for l in logs)
        # details contain attributes without secret leak
        started = next(l for l in logs if l["message"] == "trace_span_started")
        assert started["details"]["span_name"] == "my_span"
        assert started["details"]["foo"] == "bar"
        assert "trace_id" in started["details"]
        # metrics recorded
        text = generate_prometheus_text()
        assert 'node_executions_total{node="my_span",status="success"} 1' in text
        assert "node_duration_seconds_bucket" in text
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)


def test_create_span_logs_failed_and_records_failure_metric_with_secret_redaction():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        with pytest.raises(ValueError):
            with create_span("fail_span") as span:
                raise ValueError("fail with gsk_abc1234567890 and password=secret123")
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        failed = next(l for l in logs if l["message"] == "trace_span_failed")
        assert failed["level"] == "INFO" or "error" in failed  # formatted includes error
        # exc is redacted
        dumped = json.dumps(logs)
        assert "gsk_abc1234567890" not in dumped
        assert "[REDACTED_KEY]" in dumped
        assert "secret123" not in dumped
        text = generate_prometheus_text()
        assert 'node_executions_total{node="fail_span",status="failure"} 1' in text
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)


def test_create_span_propagates_explicit_trace_id():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        custom_tid = "customtrace123"
        with create_span("span_with_tid", trace_id=custom_tid):
            pass
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l.get("trace_id") == custom_tid for l in logs)
        assert any(l["details"].get("trace_id") == custom_tid for l in logs)
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)


def test_trace_llm_request_success_and_failure():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        with trace_llm_request("generate", model="test-model"):
            pass
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_llm_started" for l in logs)
        assert any(l["message"] == "trace_llm_completed" for l in logs)
        # failure path
        stream.truncate(0)
        stream.seek(0)
        with pytest.raises(RuntimeError):
            with trace_llm_request("generate_structured"):
                raise RuntimeError("LLM failed gsk_abc1234567890")
        logs2 = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_llm_failed" for l in logs2)
        assert "gsk_abc1234567890" not in json.dumps(logs2)
        assert "[REDACTED_KEY]" in json.dumps(logs2)
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)


def test_trace_tool_call_success_and_failure_with_attrs():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        with trace_tool_call("web_search", query="hello"):
            pass
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_tool_started" for l in logs)
        assert any(l["message"] == "trace_tool_completed" for l in logs)
        started = next(l for l in logs if l["message"] == "trace_tool_started")
        assert started["details"]["tool"] == "web_search"

        stream.truncate(0)
        stream.seek(0)
        with pytest.raises(ValueError):
            with trace_tool_call("web_fetch", url="https://example.com"):
                raise ValueError("tool error token=abc123 gsk_abc1234567890")
        logs2 = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_tool_failed" for l in logs2)
        assert "gsk_abc1234567890" not in json.dumps(logs2)
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)


@pytest.mark.asyncio
async def test_trace_node_decorator_async_success_and_failure():
    stream, logger, orig_h, orig_l, orig_p = _capture_logger("app.observability.tracing")
    try:
        @trace_node("my_node")
        async def success_fn(x):
            return x + 1

        @trace_node("fail_node")
        async def fail_fn(x):
            raise ValueError("node fail sk-abc1234567890")

        assert await success_fn(1) == 2
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_span_started" for l in logs)

        stream.truncate(0)
        stream.seek(0)
        reset_metrics()
        with pytest.raises(ValueError):
            await fail_fn(1)
        logs2 = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "trace_span_failed" for l in logs2)
        assert "sk-abc1234567890" not in json.dumps(logs2)
        text = generate_prometheus_text()
        # trace_node via create_span records node metric with name node.fail_node
        assert 'node.fail_node' in text
    finally:
        _restore_logger(logger, orig_h, orig_l, orig_p)
