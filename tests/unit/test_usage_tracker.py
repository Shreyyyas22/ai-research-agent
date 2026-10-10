import pytest

from app.llm.usage import UsageTracker


def test_tracker_aggregates_calls_tokens_latency_and_cost():
    tracker = UsageTracker(
        input_cost_per_million_tokens=0.10,
        output_cost_per_million_tokens=0.50,
    )

    tracker.record(
        operation="generate",
        model="test-model",
        duration_seconds=0.25,
        prompt_tokens=1000,
        completion_tokens=200,
    )
    tracker.record(
        operation="generate_structured",
        model="test-model",
        duration_seconds=0.75,
        prompt_tokens=2000,
        completion_tokens=500,
    )

    result = tracker.snapshot()

    assert result["llm_calls"] == 2
    assert result["successful_llm_calls"] == 2
    assert result["prompt_tokens"] == 3000
    assert result["completion_tokens"] == 700
    assert result["total_tokens"] == 3700
    assert result["llm_duration_seconds"] == 1.0
    assert result["estimated_cost_usd"] == pytest.approx(0.00065)
    assert result["token_usage_complete"] is True
    assert result["cost_estimate_complete"] is True


def test_tracker_does_not_invent_missing_cost():
    tracker = UsageTracker()

    tracker.record(
        operation="generate",
        model="test-model",
        duration_seconds=0.1,
        prompt_tokens=100,
        completion_tokens=50,
    )

    result = tracker.snapshot()

    assert result["llm_calls"] == 1
    assert result["total_tokens"] == 150
    assert result["estimated_cost_usd"] is None
    assert result["cost_estimate_complete"] is False


def test_tracker_records_failed_calls():
    tracker = UsageTracker()

    tracker.record(
        operation="generate",
        model="test-model",
        duration_seconds=0.2,
        succeeded=False,
    )

    result = tracker.snapshot()

    assert result["llm_calls"] == 1
    assert result["failed_llm_calls"] == 1
    assert result["successful_llm_calls"] == 0


def test_tracker_rejects_negative_prices():
    with pytest.raises(ValueError):
        UsageTracker(input_cost_per_million_tokens=-1)


def test_tracker_rejects_negative_duration():
    tracker = UsageTracker()

    with pytest.raises(ValueError):
        tracker.record(
            operation="generate",
            model="test-model",
            duration_seconds=-0.1,
        )
