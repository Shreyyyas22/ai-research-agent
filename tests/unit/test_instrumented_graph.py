
import asyncio

import pytest

from app.agents.instrumented_graph import (
    InstrumentedResearchGraph,
    ResearchRunTimeoutError,
)
from app.llm.usage import get_active_usage_tracker


class FakeGraph:
    async def ainvoke(self, input, config=None, **kwargs):
        tracker = get_active_usage_tracker()
        assert tracker is not None

        tracker.record(
            operation="test",
            model="fake-model",
            duration_seconds=0.01,
            prompt_tokens=10,
            completion_tokens=5,
        )

        await asyncio.sleep(input.get("delay", 0))
        return {"question": input["question"]}


@pytest.mark.asyncio
async def test_graph_attaches_usage_and_elapsed_time():
    graph = InstrumentedResearchGraph(FakeGraph())

    result = await graph.ainvoke({"question": "Test question"})

    assert result["usage_metadata"]["llm_calls"] == 1
    assert result["usage_metadata"]["total_tokens"] == 15
    assert result["elapsed_seconds"] >= 0
    assert result["question"] == "Test question"


@pytest.mark.asyncio
async def test_concurrent_runs_have_isolated_usage():
    graph = InstrumentedResearchGraph(FakeGraph())

    first, second = await asyncio.gather(
        graph.ainvoke({"question": "First", "delay": 0.02}),
        graph.ainvoke({"question": "Second", "delay": 0.01}),
    )

    assert first["usage_metadata"]["llm_calls"] == 1
    assert second["usage_metadata"]["llm_calls"] == 1
    assert first["usage_metadata"]["calls"][0]["model"] == "fake-model"
    assert second["usage_metadata"]["calls"][0]["model"] == "fake-model"
    assert first["question"] == "First"
    assert second["question"] == "Second"


@pytest.mark.asyncio
async def test_graph_restores_tracking_context_after_run():
    graph = InstrumentedResearchGraph(FakeGraph())

    assert get_active_usage_tracker() is None

    await graph.ainvoke({"question": "Test"})

    assert get_active_usage_tracker() is None


@pytest.mark.asyncio
async def test_graph_raises_timeout_error_when_exceeding_max_research_time():
    graph = InstrumentedResearchGraph(FakeGraph(), max_research_time=0.05)

    with pytest.raises(ResearchRunTimeoutError) as exc_info:
        await graph.ainvoke({"question": "Slow run", "delay": 0.2})

    assert "exceeded maximum duration" in str(exc_info.value)


def test_graph_rejects_invalid_max_research_time():
    with pytest.raises(ValueError, match="MAX_RESEARCH_TIME must be greater than zero"):
        InstrumentedResearchGraph(FakeGraph(), max_research_time=0)

    with pytest.raises(ValueError, match="MAX_RESEARCH_TIME must be greater than zero"):
        InstrumentedResearchGraph(FakeGraph(), max_research_time=-5)


@pytest.mark.asyncio
async def test_graph_restores_tracking_context_after_timeout():
    graph = InstrumentedResearchGraph(FakeGraph(), max_research_time=0.05)

    assert get_active_usage_tracker() is None

    with pytest.raises(ResearchRunTimeoutError):
        await graph.ainvoke({"question": "Timeout test", "delay": 0.2})

    assert get_active_usage_tracker() is None


from app.tools.tracker import get_active_tool_call_tracker


class MultiNodeFakeGraph:
    async def ainvoke(self, input, config=None, **kwargs):
        tracker = get_active_tool_call_tracker()
        assert tracker is not None

        # Simulate 3 tool calls across node cycles within the same run
        res1 = await tracker.try_reserve()
        res2 = await tracker.try_reserve()
        res3 = await tracker.try_reserve()

        return {
            "question": input["question"],
            "reservations": [res1, res2, res3],
            "count": tracker.count,
        }


@pytest.mark.asyncio
async def test_tool_call_tracker_persists_across_nodes_and_enforces_limit():
    graph = InstrumentedResearchGraph(MultiNodeFakeGraph(), max_tool_calls=2)

    result = await graph.ainvoke({"question": "Multi node test"})

    assert result["reservations"] == [True, True, False]
    assert result["count"] == 2
    assert get_active_tool_call_tracker() is None


@pytest.mark.asyncio
async def test_concurrent_runs_have_isolated_tool_call_trackers():
    graph1 = InstrumentedResearchGraph(MultiNodeFakeGraph(), max_tool_calls=2)
    graph2 = InstrumentedResearchGraph(MultiNodeFakeGraph(), max_tool_calls=3)

    first, second = await asyncio.gather(
        graph1.ainvoke({"question": "First"}),
        graph2.ainvoke({"question": "Second"}),
    )

    assert first["reservations"] == [True, True, False]
    assert first["count"] == 2

    assert second["reservations"] == [True, True, True]
    assert second["count"] == 3

    assert get_active_tool_call_tracker() is None


def test_instrumented_graph_configures_max_agent_iterations():
    graph = InstrumentedResearchGraph(FakeGraph(), max_agent_iterations=5)
    assert graph.max_agent_iterations == 5


def test_instrumented_graph_rejects_invalid_max_agent_iterations():
    with pytest.raises(ValueError, match="MAX_AGENT_ITERATIONS must be at least 1"):
        InstrumentedResearchGraph(FakeGraph(), max_agent_iterations=0)

    with pytest.raises(ValueError, match="MAX_AGENT_ITERATIONS must be at least 1"):
        InstrumentedResearchGraph(FakeGraph(), max_agent_iterations=-1)



