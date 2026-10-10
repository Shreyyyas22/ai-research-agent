"""Failure & resilience integration — provider failures, timeouts, retries, malformed outputs, limit exhaustion."""

import asyncio
import io
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.agents.graph import build_research_graph
from app.agents.researcher import Researcher
from app.llm.groq import ContextWindowExceededError, GroqProvider
from app.llm.usage import LLMCallLimitExceeded, UsageTracker, use_usage_tracker
from app.observability.logging import JSONFormatter
from app.observability.metrics import generate_prometheus_text, reset_metrics
from app.schemas.research import (
    EvidenceExtraction,
    EvidenceSufficiency,
    ReportEvaluation,
    ResearchPlan,
    ResearchTask,
    SourceEvaluation,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.citation_service import CitationService
from app.services.report_service import ReportService
from app.services.research_service import ResearchService
from app.tools.schemas import SearchResponse, SearchResult
from app.tools.web_search import WebSearchTool


def make_response(content, prompt_tokens=5, completion_tokens=5):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def make_groq_provider(tracker=None, max_context_size=None):
    p = GroqProvider.__new__(GroqProvider)
    p.model = "test-model"
    p.usage_tracker = tracker or UsageTracker()
    p.max_context_size = max_context_size
    p.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())))
    return p


class FlakySearchProvider:
    """First call fails, second succeeds — tests retry/isolation."""

    def __init__(self):
        self.calls = 0

    async def search(self, query):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("Provider unavailable gsk_abc1234567890")
        return SearchResponse(
            success=True,
            results=[SearchResult(title="t", url="https://example.com/a", snippet="s")],
        )


class FakePlanner:
    async def create_plan(self, question):
        return ResearchPlan(tasks=[ResearchTask(question=question, search_queries=["q1"], priority=1)])


class FakeFetchTool:
    async def execute(self, input):
        return {"success": True, "content": "evidence content"}


class FakeEval:
    async def evaluate(self, question, evidence, llm_provider):
        return SourceEvaluation(
            sufficiency=EvidenceSufficiency(sufficient=True, reasoning="ok"),
            conflicts=[],
        )


class FakeSynth:
    async def synthesize(self, question, evidence, conflicts, llm_provider):
        return SynthesisResult(claims=[SynthesizedClaim(claim=evidence[0].claim, citation_ids=[1])])


class FakeReportEval:
    async def evaluate(self, question, report, evidence, llm_provider):
        return ReportEvaluation(grounded=True, citation_correct=True, hallucination_detected=False, score=5, reasoning="ok")


class FakeLLMForGraph:
    async def generate_structured(self, messages, response_model):
        if response_model is EvidenceExtraction:
            return EvidenceExtraction(evidence=[{"claim": "c1", "excerpt": "e1"}])
        raise NotImplementedError


@pytest.fixture(autouse=True)
def _reset_metrics():
    reset_metrics()
    yield
    reset_metrics()


@pytest.mark.asyncio
async def test_e2e_with_retry_on_provider_failure_still_succeeds():
    provider = FlakySearchProvider()
    researcher = Researcher(tools={"web_search": WebSearchTool(provider)}, max_execution_time=1)
    graph = build_research_graph(
        researcher=researcher,
        research_service=ResearchService(),
        planner=FakePlanner(),
        evaluation_service=FakeEval(),
        llm_provider=FakeLLMForGraph(),
        synthesizer=FakeSynth(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=FakeReportEval(),
        web_fetch_tool=FakeFetchTool(),
    )
    # First task will hit flaky provider but researcher isolates failure per query — graph should still succeed
    # Use two queries to exercise isolation
    class Planner2:
        async def create_plan(self, question):
            return ResearchPlan(
                tasks=[ResearchTask(question=question, search_queries=["fail query", "good query"], priority=1)]
            )

    graph2 = build_research_graph(
        researcher=Researcher(tools={"web_search": WebSearchTool(FlakySearchProvider())}),
        research_service=ResearchService(),
        planner=Planner2(),
        evaluation_service=FakeEval(),
        llm_provider=FakeLLMForGraph(),
        synthesizer=FakeSynth(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=FakeReportEval(),
        web_fetch_tool=FakeFetchTool(),
    )
    result = await graph2.ainvoke({"question": "test question"})
    assert result["research_sufficient"] is True
    assert result["citations"] == [1]
    # metrics should show a run and possibly node executions
    text = generate_prometheus_text()
    assert 'research_runs_total{status="success"}' in text


@pytest.mark.asyncio
async def test_groq_malformed_structured_retry_exhaustion_is_recorded():
    provider = make_groq_provider()
    # first returns invalid json, second also invalid → should raise ValidationError after 2 attempts
    provider.client.chat.completions.create.side_effect = [
        make_response('{"answer": 123}'),
        make_response('not json at all'),
    ]

    class BadModel(BaseModel):
        answer: str

    with pytest.raises(Exception):
        await provider.generate_structured([{"role": "user", "content": "hi"}], BadModel)

    snap = provider.usage_tracker.snapshot()
    # both attempts counted
    assert snap["llm_calls"] == 2
    assert snap["failed_llm_calls"] == 0  # validation failure is not a transport failure, but calls still succeed
    # metrics should have recorded 2 requests
    text = generate_prometheus_text()
    assert "llm_requests_total" in text


@pytest.mark.asyncio
async def test_groq_provider_timeout_and_failure_are_recorded_with_metrics():
    provider = make_groq_provider()
    provider.client.chat.completions.create.side_effect = RuntimeError("API down")
    with pytest.raises(RuntimeError):
        await provider.generate([{"role": "user", "content": "hi"}])
    snap = provider.usage_tracker.snapshot()
    assert snap["failed_llm_calls"] == 1
    text = generate_prometheus_text()
    assert "llm_errors_total" in text
    # failure increments llm_requests_total with status=failure
    assert 'llm_requests_total' in text
    assert 'status="failure"' in text


@pytest.mark.asyncio
async def test_context_window_exceeded_is_limit_violation_and_metric():
    provider = make_groq_provider(max_context_size=2)
    with pytest.raises(ContextWindowExceededError):
        await provider.generate([{"role": "user", "content": "A" * 100}])
    text = generate_prometheus_text()
    assert 'limit_violations_total{limit="max_context_size"}' in text
    # usage tracker should not have incremented call count for rejected request
    assert provider.usage_tracker.snapshot()["llm_calls"] == 0


@pytest.mark.asyncio
async def test_llm_call_limit_exhaustion_is_isolated_and_logged_without_secret():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("app.llm")
    orig_h, orig_l, orig_p = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    try:
        tracker = UsageTracker(max_llm_calls=1)
        provider = make_groq_provider(tracker=tracker)
        provider.client.chat.completions.create.return_value = make_response("ok")
        # first succeeds
        await provider.generate([{"role": "user", "content": "hi"}])
        # second hits limit before API call
        with pytest.raises(LLMCallLimitExceeded):
            await provider.generate([{"role": "user", "content": "hi with gsk_abc1234567890"}])
        logs = stream.getvalue()
        assert "limit_violation" in logs
        assert "gsk_abc1234567890" not in logs
        assert "[REDACTED_KEY]" in logs or "max_llm_calls" in logs
        text = generate_prometheus_text()
        assert 'limit_violations_total{limit="max_llm_calls"}' in text
        assert "gsk_abc1234567890" not in text
    finally:
        logger.handlers = orig_h
        logger.setLevel(orig_l)
        logger.propagate = orig_p


@pytest.mark.asyncio
async def test_graph_timeout_is_metric_and_log_without_secret():
    from app.agents.instrumented_graph import InstrumentedResearchGraph, ResearchRunTimeoutError

    class SlowGraph:
        async def ainvoke(self, *a, **kw):
            await asyncio.sleep(0.3)
            return {}

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("app.agents.instrumented_graph")
    orig_h, orig_l, orig_p = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        graph = InstrumentedResearchGraph(SlowGraph(), max_research_time=0.05)
        with pytest.raises(ResearchRunTimeoutError):
            await graph.ainvoke({"question": "slow gsk_abc1234567890"})
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        assert any(l["message"] == "research_run_timeout" for l in logs)
        assert "gsk_abc1234567890" not in json.dumps(logs)
        text = generate_prometheus_text()
        assert 'research_runs_total{status="timeout"}' in text
        assert 'limit_violations_total{limit="max_research_time"}' in text
    finally:
        logger.handlers = orig_h
        logger.setLevel(orig_l)
        logger.propagate = orig_p


@pytest.mark.asyncio
async def test_graph_failure_is_metric_and_preserves_trace_context():
    from app.agents.instrumented_graph import InstrumentedResearchGraph

    class FailGraph:
        async def ainvoke(self, *a, **kw):
            raise ValueError("boom gsk_abc1234567890")

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONFormatter())
    logger = logging.getLogger("app.agents.instrumented_graph")
    orig_h, orig_l, orig_p = logger.handlers[:], logger.level, logger.propagate
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        graph = InstrumentedResearchGraph(FailGraph())
        with pytest.raises(ValueError):
            await graph.ainvoke({"question": "fail", "run_id": "run-123"}, config={"trace_id": "trace-xyz"})
        logs = [json.loads(l) for l in stream.getvalue().strip().split("\n") if l]
        failed = next(l for l in logs if l["message"] == "research_run_failed")
        assert failed["run_id"] == "run-123"
        assert failed["trace_id"] == "trace-xyz"
        assert "gsk_abc1234567890" not in json.dumps(logs)
        assert "[REDACTED_KEY]" in json.dumps(logs)
        text = generate_prometheus_text()
        assert 'research_runs_total{status="failure"}' in text
    finally:
        logger.handlers = orig_h
        logger.setLevel(orig_l)
        logger.propagate = orig_p
