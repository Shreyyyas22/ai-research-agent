"""Targeted coverage for app/observability/metrics — request counts, latency, errors, tokens, limits + Prometheus."""

import pytest

from app.observability.metrics import (
    generate_prometheus_text,
    get_metrics_snapshot,
    inc_counter,
    metrics_endpoint_content,
    observe_histogram,
    record_limit_violation,
    record_llm_request,
    record_node_execution,
    record_research_run,
    record_tool_call,
    reset_metrics,
    set_gauge,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    yield
    reset_metrics()


def test_inc_counter_and_negative_rejected():
    inc_counter("research_runs_total", {"status": "success"}, 1)
    inc_counter("research_runs_total", {"status": "success"}, 2)
    snap = get_metrics_snapshot()
    assert snap["counters"]["research_runs_total"]["status=success"] == 3
    with pytest.raises(ValueError):
        inc_counter("research_runs_total", value=-1)


def test_observe_histogram_negative_rejected_and_buckets():
    observe_histogram("research_run_duration_seconds", 0.04)
    observe_histogram("research_run_duration_seconds", 0.6)
    # also with labels
    observe_histogram("llm_request_duration_seconds", 0.2, {"operation": "generate"})
    text = generate_prometheus_text()
    assert "research_run_duration_seconds_bucket" in text
    assert "research_run_duration_seconds_count" in text
    assert "research_run_duration_seconds_sum" in text
    assert "le=\"0.05\"" in text
    assert "le=\"+Inf\"" in text
    with pytest.raises(ValueError):
        observe_histogram("research_run_duration_seconds", -0.1)


def test_secret_redaction_in_labels_and_values():
    # gsk_ secret must be redacted when used as label value
    inc_counter("llm_requests_total", {"model": "gsk_abc1234567890", "operation": "generate", "status": "success"}, 1)
    inc_counter("limit_violations_total", {"limit": "gsk_abc1234567890"}, 1)
    text = generate_prometheus_text()
    assert "gsk_abc1234567890" not in text
    assert "[REDACTED_KEY]" in text
    # value redaction: Bearer token in counter value string representation
    inc_counter("tool_calls_total", {"tool": "Bearer abc.def.ghi"}, 1)
    text2 = generate_prometheus_text()
    assert "Bearer abc.def.ghi" not in text2
    assert "Bearer [REDACTED]" in text2


def test_record_research_run_branches():
    record_research_run(0.5, "success")
    record_research_run(0.8, "failure")
    record_research_run(1.2, "timeout")
    snap = get_metrics_snapshot()
    assert snap["counters"]["research_runs_total"]["status=success"] == 1
    assert snap["counters"]["research_runs_total"]["status=failure"] == 1
    assert snap["counters"]["research_runs_total"]["status=timeout"] == 1
    assert snap["counters"]["research_errors_total"]["status=failure"] == 1
    assert snap["counters"]["research_timeouts_total"]["__total__"] == 1
    assert snap["counters"]["limit_violations_total"]["limit=max_research_time"] == 1
    text = generate_prometheus_text()
    assert "research_run_duration_seconds_bucket" in text
    # HELP/TYPE present even for histogram
    assert '# HELP research_run_duration_seconds' in text


def test_record_llm_request_all_paths():
    # successful with tokens
    record_llm_request(0.3, operation="generate", model="test-model", succeeded=True, prompt_tokens=10, completion_tokens=20)
    # failure without tokens
    record_llm_request(0.1, operation="generate", succeeded=False)
    # successful without model
    record_llm_request(0.05, succeeded=True)
    # with negative tokens ignored, zero tokens counted
    record_llm_request(0.02, succeeded=True, prompt_tokens=0, completion_tokens=0)
    snap = get_metrics_snapshot()
    # llm_requests_total should have 4 increments grouped by labels
    assert sum(snap["counters"]["llm_requests_total"].values()) == 4
    # llm_errors_total only for the failure
    assert snap["counters"]["llm_errors_total"]["operation=generate"] == 1
    # llm_tokens_total for prompt/completion
    assert snap["counters"]["llm_tokens_total"]["type=prompt"] == 10
    assert snap["counters"]["llm_tokens_total"]["type=completion"] == 20
    text = generate_prometheus_text()
    assert "llm_tokens_total" in text
    assert "llm_request_duration_seconds_bucket" in text


def test_record_tool_and_node_and_limit():
    record_tool_call(2, {"tool": "web_search"})
    record_tool_call(1)
    record_limit_violation("max_tool_calls")
    record_limit_violation("max_llm_calls")
    record_node_execution("execute_tasks", 0.12, succeeded=True)
    record_node_execution("execute_tasks", 0.2, succeeded=False)
    snap = get_metrics_snapshot()
    assert snap["counters"]["tool_calls_total"]["tool=web_search"] == 2
    assert snap["counters"]["limit_violations_total"]["limit=max_tool_calls"] == 1
    assert snap["counters"]["node_executions_total"]["node=execute_tasks,status=success"] == 1
    assert snap["counters"]["node_executions_total"]["node=execute_tasks,status=failure"] == 1
    # failure also increments research_errors_total with node label
    assert snap["counters"]["research_errors_total"]["node=execute_tasks"] == 1
    text = generate_prometheus_text()
    assert 'node_executions_total{node="execute_tasks"' in text
    assert "node_duration_seconds_bucket" in text


def test_set_gauge_and_snapshot_decoding():
    set_gauge("research_run_duration_seconds", 1.23, {"status": "gauge"})
    snap = get_metrics_snapshot()
    # gauge stored separately
    assert "research_run_duration_seconds" in snap["gauges"]
    text = generate_prometheus_text()
    assert "1.23" in text


def test_generate_prometheus_exposes_help_even_without_samples():
    # reset already, generate should still emit HELP/TYPE for known metrics
    text = generate_prometheus_text()
    assert "# HELP research_runs_total Total research graph runs" in text
    assert "# TYPE research_runs_total counter" in text
    assert "# HELP research_run_duration_seconds" in text
    # final newline per spec
    assert text.endswith("\n")


def test_metrics_endpoint_content_no_secret_leak():
    inc_counter("research_runs_total", {"status": "success"}, 1)
    inc_counter("limit_violations_total", {"limit": "sk-abc1234567890"}, 1)
    ctype, body = metrics_endpoint_content()
    assert ctype == "text/plain; version=0.0.4; charset=utf-8"
    assert "research_runs_total" in body
    assert "sk-abc1234567890" not in body
    assert "[REDACTED_KEY]" in body


def test_get_metrics_snapshot_structure():
    inc_counter("research_runs_total", {"status": "success"}, 5)
    observe_histogram("research_run_duration_seconds", 0.3)
    set_gauge("tool_calls_total", 42)
    snap = get_metrics_snapshot()
    assert "counters" in snap and "histograms" in snap and "gauges" in snap
    # histogram entry has count/sum/bucket_*
    hist_key = next(iter(snap["histograms"]["research_run_duration_seconds"]))
    entry = snap["histograms"]["research_run_duration_seconds"][hist_key]
    assert entry["count"] == 1
    assert entry["sum"] == 0.3
    assert "bucket_0.05" in entry
