"""Concurrency — run-scoped UsageTracker, ToolCallTracker, metrics, and logging context isolation."""

import asyncio
import io
import json
import logging

import pytest

from app.agents.instrumented_graph import InstrumentedResearchGraph
from app.llm.usage import UsageTracker, get_active_usage_tracker, use_usage_tracker
from app.observability.logging import JSONFormatter, bind_logging_context, get_current_run_id
from app.observability.metrics import generate_prometheus_text, reset_metrics
from app.tools.tracker import ToolCallTracker, get_active_tool_call_tracker, use_tool_call_tracker


@pytest.fixture(autouse=True)
def _reset():
    reset_metrics()
    yield
    reset_metrics()


@pytest.mark.asyncio
async def test_concurrent_usage_trackers_isolated_via_contextvar():
    tracker_a = UsageTracker()
    tracker_b = UsageTracker()

    async def task(tracker, delay, tokens):
        with use_usage_tracker(tracker):
            await asyncio.sleep(delay)
            tracker.record(operation="generate", model="m", duration_seconds=0.01, prompt_tokens=tokens, completion_tokens=tokens)
            # ensure active tracker is the one we set
            assert get_active_usage_tracker() is tracker
            return tracker.snapshot()["total_tokens"]

    a, b = await asyncio.gather(task(tracker_a, 0.02, 10), task(tracker_b, 0.01, 20))
    assert a == 20
    assert b == 40
    # after gather, no active tracker leaks
    assert get_active_usage_tracker() is None
    # trackers are independent
    assert tracker_a.snapshot()["total_tokens"] == 20
    assert tracker_b.snapshot()["total_tokens"] == 40


@pytest.mark.asyncio
async def test_concurrent_tool_trackers_isolated():
    tracker_a = ToolCallTracker(max_tool_calls=2)
    tracker_b = ToolCallTracker(max_tool_calls=5)

    async def use_tracker(tracker, n):
        with use_tool_call_tracker(tracker):
            results = []
            for _ in range(n):
                results.append(await tracker.try_reserve())
            assert get_active_tool_call_tracker() is tracker
            return results

    r1, r2 = await asyncio.gather(use_tracker(tracker_a, 3), use_tracker(tracker_b, 3))
    assert r1 == [True, True, False]
    assert r2 == [True, True, True]
    assert get_active_tool_call_tracker() is None


@pytest.mark.asyncio
async def test_instrumented_graph_concurrent_metrics_aggregation_without_secret_leak():
    class FakeGraph:
        async def ainvoke(self, input, config=None, **kwargs):
            tracker = get_active_usage_tracker()
            tracker.record(operation="generate", model="fake", duration_seconds=0.01, prompt_tokens=5, completion_tokens=5)
            await asyncio.sleep(input.get("delay", 0))
            return {"question": input["question"]}

    graph = InstrumentedResearchGraph(FakeGraph())
    # include secret in question to test redaction
    a, b = await asyncio.gather(
        graph.ainvoke({"question": "hello gsk_abc1234567890", "delay": 0.02}),
        graph.ainvoke({"question": "world sk-abc1234567890", "delay": 0.01}),
    )
    assert a["usage_metadata"]["llm_calls"] == 1
    assert b["usage_metadata"]["llm_calls"] == 1
    text = generate_prometheus_text()
    assert text.count('research_runs_total{status="success"}') == 1
    # Prometheus aggregates: should be 2
    assert 'research_runs_total{status="success"} 2' in text
    assert "gsk_abc1234567890" not in text
    assert "sk-abc1234567890" not in text
    # metrics should have llm tokens but no secret
    assert "llm_tokens_total" in text


@pytest.mark.asyncio
async def test_logging_context_isolated_across_concurrent_tasks():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("test_conc_logger")
    orig_h, orig_l, orig_p = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        async def log_task(run_id, delay):
            with bind_logging_context(run_id=run_id, trace_id=f"trace-{run_id}"):
                await asyncio.sleep(delay)
                logger.info(f"message for {run_id} with gsk_abc1234567890")
                # inside context, get_current_run_id matches
                assert get_current_run_id() == run_id

        await asyncio.gather(log_task("run-a", 0.02), log_task("run-b", 0.01))
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert len(logs) == 2
        run_ids = {l["run_id"] for l in logs}
        assert run_ids == {"run-a", "run-b"}
        # secrets redacted
        assert "gsk_abc1234567890" not in json.dumps(logs)
        assert "[REDACTED_KEY]" in json.dumps(logs)
        # outside context no leak
        assert get_current_run_id() is None
    finally:
        logger.handlers = orig_h
        logger.setLevel(orig_l)
        logger.propagate = orig_p


@pytest.mark.asyncio
async def test_metrics_counter_is_threadsafe_under_concurrency():
    # stress inc_counter from many concurrent tasks
    from app.observability.metrics import inc_counter

    async def inc_many(n):
        for _ in range(n):
            inc_counter("tool_calls_total", {"tool": "web_search"})
            await asyncio.sleep(0)

    await asyncio.gather(*(inc_many(20) for _ in range(5)))
    text = generate_prometheus_text()
    # 5*20 =100
    assert 'tool_calls_total{tool="web_search"} 100' in text


def test_usage_tracker_reserve_is_threadsafe():
    import threading

    tracker = UsageTracker(max_llm_calls=100)
    errors = []

    def reserve_many():
        for _ in range(20):
            try:
                tracker.reserve_call()
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=reserve_many) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # 5*20 =100, no error
    assert not errors
    assert tracker._started_calls == 100
    # one more should exceed
    with pytest.raises(Exception):
        tracker.reserve_call()
