import io
import json
import logging

import pytest

from app.observability.logging import (
    JSONFormatter,
    bind_logging_context,
    configure_logging,
    redact_secrets,
)


def test_redact_secrets_removes_api_keys_and_passwords():
    raw_text = "Connecting with gsk_abcdef123456789 and password=mysecretpassword"
    redacted = redact_secrets(raw_text)

    assert "gsk_abcdef123456789" not in redacted
    assert "mysecretpassword" not in redacted
    assert "[REDACTED_KEY]" in redacted
    assert "[REDACTED]" in redacted


def test_json_formatter_outputs_valid_json_fields():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)

    logger.info("Test message", extra={"custom_field": "value123"})

    log_output = stream.getvalue().strip()
    data = json.loads(log_output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test message"
    assert data["details"]["custom_field"] == "value123"
    assert "timestamp" in data


def test_bind_logging_context_attaches_context_fields():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_context_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)

    with bind_logging_context(run_id="run-101", trace_id="trace-abc", node_name="execute_tasks"):
        logger.info("Executing tasks node")

    log_output = stream.getvalue().strip()
    data = json.loads(log_output)

    assert data["run_id"] == "run-101"
    assert data["trace_id"] == "trace-abc"
    assert data["node_name"] == "execute_tasks"


def test_json_formatter_captures_exceptions():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("test_exc_logger")
    logger.handlers = [handler]
    logger.setLevel(logging.ERROR)

    try:
        raise ValueError("Invalid argument with gsk_secretkey12345")
    except Exception as exc:
        logger.error("An error occurred", exc_info=exc)

    log_output = stream.getvalue().strip()
    data = json.loads(log_output)

    assert data["level"] == "ERROR"
    assert "error" in data
    assert data["error"]["type"] == "ValueError"
    assert "gsk_secretkey12345" not in data["error"]["message"]
    assert "[REDACTED_KEY]" in data["error"]["message"]
    assert "stack_trace" in data["error"]
