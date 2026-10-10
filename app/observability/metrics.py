from __future__ import annotations

import threading
import time
from typing import Any

# Global registry — stdlib only, no prometheus_client required.
_LOCK = threading.Lock()

# Counter storage: name -> {frozenset(labels): value}
_COUNTERS: dict[str, dict[frozenset[tuple[str, str]], float]] = {}
# Histogram/Summary storage: name -> {labels_key: {count, sum, buckets?}}
_HISTOGRAMS: dict[str, dict[frozenset[tuple[str, str]], dict[str, float]]] = {}
_GAUGES: dict[str, dict[frozenset[tuple[str, str]], float]] = {}

# Metadata for HELP/TYPE exposition
_HELP: dict[str, str] = {
    "research_runs_total": "Total research graph runs",
    "research_run_duration_seconds": "Research run latency in seconds",
    "research_errors_total": "Total research run errors",
    "research_timeouts_total": "Total research run timeouts",
    "llm_requests_total": "Total LLM requests",
    "llm_request_duration_seconds": "LLM request latency in seconds",
    "llm_tokens_total": "Total LLM tokens",
    "llm_errors_total": "Total LLM request errors",
    "tool_calls_total": "Total tool calls",
    "limit_violations_total": "Total resource limit violations",
    "node_executions_total": "Total graph node executions",
    "node_duration_seconds": "Graph node execution latency",
}

_TYPE: dict[str, str] = {
    "research_runs_total": "counter",
    "research_run_duration_seconds": "histogram",
    "research_errors_total": "counter",
    "research_timeouts_total": "counter",
    "llm_requests_total": "counter",
    "llm_request_duration_seconds": "histogram",
    "llm_tokens_total": "counter",
    "llm_errors_total": "counter",
    "tool_calls_total": "counter",
    "limit_violations_total": "counter",
    "node_executions_total": "counter",
    "node_duration_seconds": "histogram",
}

# Default buckets for histograms (seconds)
_DEFAULT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)


def _labels_key(labels: dict[str, str] | None) -> frozenset[tuple[str, str]]:
    if not labels:
        return frozenset()
    # Redact any secret-like values before storing as label
    # Keep labels fixed and low-cardinality; values are sanitized
    from app.observability.logging import redact_secrets

    cleaned: dict[str, str] = {}
    for k, v in labels.items():
        # labels should be small, known strings — redact just in case
        sv = str(v)
        # don't store raw secrets in metrics
        cleaned[k] = redact_secrets(sv)
    return frozenset(sorted(cleaned.items()))


def _labels_str(key: frozenset[tuple[str, str]]) -> str:
    if not key:
        return ""
    parts = [f'{k}="{v}"' for k, v in sorted(key)]
    return "{" + ",".join(parts) + "}"


def inc_counter(name: str, labels: dict[str, str] | None = None, value: float = 1) -> None:
    """Increment a counter metric."""
    if value < 0:
        raise ValueError("counter increment cannot be negative")
    key = _labels_key(labels)
    with _LOCK:
        bucket = _COUNTERS.setdefault(name, {})
        bucket[key] = bucket.get(key, 0) + value


def set_gauge(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    key = _labels_key(labels)
    with _LOCK:
        bucket = _GAUGES.setdefault(name, {})
        bucket[key] = value


def observe_histogram(name: str, value: float, labels: dict[str, str] | None = None) -> None:
    """Observe a histogram value (also tracks count/sum)."""
    if value < 0:
        # latency can be zero but not negative
        raise ValueError("histogram observation cannot be negative")
    key = _labels_key(labels)
    with _LOCK:
        bucket = _HISTOGRAMS.setdefault(name, {})
        entry = bucket.get(key)
        if entry is None:
            entry = {"count": 0, "sum": 0.0}
            # initialize bucket counts
            for b in _DEFAULT_BUCKETS:
                entry[f"bucket_{b}"] = 0
            entry["bucket_inf"] = 0
            bucket[key] = entry
        entry["count"] += 1
        entry["sum"] += value
        for b in _DEFAULT_BUCKETS:
            if value <= b:
                entry[f"bucket_{b}"] += 1
        entry["bucket_inf"] += 1


def reset_metrics() -> None:
    """Reset all metrics — used in tests."""
    with _LOCK:
        _COUNTERS.clear()
        _HISTOGRAMS.clear()
        _GAUGES.clear()


def get_metrics_snapshot() -> dict[str, Any]:
    """Return a snapshot of current metrics for testing."""
    with _LOCK:
        # deep copy
        counters = {k: dict(v) for k, v in _COUNTERS.items()}
        histograms = {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in _HISTOGRAMS.items()}
        gauges = {k: dict(v) for k, v in _GAUGES.items()}
    # convert frozenset keys to dict labels for readability
    def _decode(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            label_dict = dict(k) if k else {}
            label_str = ",".join(f"{a}={b}" for a, b in sorted(label_dict.items())) if label_dict else "__total__"
            out[label_str] = v
        return out

    return {
        "counters": {k: _decode(v) for k, v in counters.items()},
        "histograms": histograms,
        "gauges": gauges,
    }


def generate_prometheus_text() -> str:
    """Generate Prometheus text exposition format (0.0.4). No secret leakage."""
    from app.observability.logging import redact_secrets

    lines: list[str] = []
    with _LOCK:
        # Counters
        for name in sorted(set(list(_COUNTERS.keys()) + list(_HELP.keys()))):
            if name not in _COUNTERS and name not in _HISTOGRAMS and name not in _GAUGES:
                # expose HELP/TYPE even if no samples yet (helps scraping)
                help_text = _HELP.get(name, "")
                type_text = _TYPE.get(name, "counter")
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                    lines.append(f"# TYPE {name} {type_text}")
                continue
            if name in _COUNTERS:
                help_text = _HELP.get(name, "")
                type_text = _TYPE.get(name, "counter")
                if help_text:
                    lines.append(f"# HELP {name} {help_text}")
                    lines.append(f"# TYPE {name} {type_text}")
                for key, value in sorted(_COUNTERS[name].items(), key=lambda x: sorted(x[0])):
                    # redact value string representation just in case
                    val_str = redact_secrets(str(value))
                    lines.append(f"{name}{_labels_str(key)} {val_str}")
        # Histograms
        for name, buckets in sorted(_HISTOGRAMS.items()):
            help_text = _HELP.get(name, "")
            type_text = _TYPE.get(name, "histogram")
            if help_text:
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {type_text}")
            for key, entry in sorted(buckets.items(), key=lambda x: sorted(x[0])):
                label_dict = dict(key)
                for b in _DEFAULT_BUCKETS:
                    bucket_labels = dict(label_dict)
                    bucket_labels["le"] = str(b)
                    bucket_key = frozenset(sorted(bucket_labels.items()))
                    lines.append(f"{name}_bucket{_labels_str(bucket_key)} {entry[f'bucket_{b}']}")
                # +Inf bucket
                inf_labels = dict(label_dict)
                inf_labels["le"] = "+Inf"
                inf_key = frozenset(sorted(inf_labels.items()))
                lines.append(f"{name}_bucket{_labels_str(inf_key)} {entry['bucket_inf']}")
                lines.append(f"{name}_count{_labels_str(key)} {entry['count']}")
                lines.append(f"{name}_sum{_labels_str(key)} {entry['sum']}")
        # Gauges
        for name, buckets in sorted(_GAUGES.items()):
            help_text = _HELP.get(name, "")
            type_text = _TYPE.get(name, "gauge")
            if help_text:
                lines.append(f"# HELP {name} {help_text}")
                lines.append(f"# TYPE {name} {type_text}")
            for key, value in sorted(buckets.items(), key=lambda x: sorted(x[0])):
                lines.append(f"{name}{_labels_str(key)} {value}")

    # Ensure final newline per Prometheus spec
    if lines and not lines[-1].endswith("\n"):
        return "\n".join(lines) + "\n"
    return "\n".join(lines)


# Convenience helpers for common metrics

def record_research_run(duration: float, status: str) -> None:
    """status: success, failure, timeout"""
    inc_counter("research_runs_total", {"status": status})
    if status == "failure":
        inc_counter("research_errors_total", {"status": status})
    if status == "timeout":
        inc_counter("research_timeouts_total", {})
        inc_counter("limit_violations_total", {"limit": "max_research_time"})
    observe_histogram("research_run_duration_seconds", duration)


def record_llm_request(
    duration: float | None = None,
    operation: str | None = None,
    model: str | None = None,
    succeeded: bool = True,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    duration_seconds: float | None = None,
) -> None:
    # alias handling for duration_seconds vs duration
    if duration is None:
        duration = duration_seconds
    if duration is None:
        raise ValueError("duration must be provided")
    labels: dict[str, str] = {}
    if operation:
        labels["operation"] = operation
    if model:
        labels["model"] = model
    # status label keeps cardinality low
    labels["status"] = "success" if succeeded else "failure"
    inc_counter("llm_requests_total", labels)
    observe_histogram("llm_request_duration_seconds", duration, {"operation": operation} if operation else None)
    if not succeeded:
        inc_counter("llm_errors_total", {"operation": operation} if operation else None)
    if prompt_tokens is not None and prompt_tokens >= 0:
        inc_counter("llm_tokens_total", {"type": "prompt"}, prompt_tokens)
    if completion_tokens is not None and completion_tokens >= 0:
        inc_counter("llm_tokens_total", {"type": "completion"}, completion_tokens)


def record_tool_call(count: int = 1, labels: dict[str, str] | None = None) -> None:
    inc_counter("tool_calls_total", labels, count)


def record_limit_violation(limit: str) -> None:
    inc_counter("limit_violations_total", {"limit": limit})


def record_node_execution(node_name: str, duration: float, succeeded: bool = True) -> None:
    inc_counter("node_executions_total", {"node": node_name, "status": "success" if succeeded else "failure"})
    observe_histogram("node_duration_seconds", duration, {"node": node_name})
    if not succeeded:
        inc_counter("research_errors_total", {"node": node_name})


# Metrics middleware helper
def metrics_endpoint_content() -> tuple[str, str]:
    """Return (content_type, body) for /metrics."""
    return ("text/plain; version=0.0.4; charset=utf-8", generate_prometheus_text())
