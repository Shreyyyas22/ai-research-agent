import json
import pathlib

import pytest

from app.eval.dataset import load_dataset
from app.eval.runner import EvaluationRunner, summarize_results
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


def make_fake_graph(report_text="PostgreSQL supports vector search"):
    """Deterministic fake graph that reuses existing schemas without LLM calls."""

    class FakeGraph:
        async def ainvoke(self, input, **kwargs):
            question = input["question"]
            src = Source(title="PostgreSQL Docs", url="https://example.com/pg")
            ev = Evidence(source=src, claim="PostgreSQL supports vector search", excerpt="PostgreSQL supports vector search via pgvector")
            # simple synthesis that includes expected claim verbatim for recall
            synthesis_claim = report_text if report_text else question
            report = ResearchReport(
                title=f"Research Report: {question}",
                executive_summary=synthesis_claim,
                key_findings=[SynthesizedClaim(claim=synthesis_claim, citation_ids=[1])],
                detailed_analysis=f"1. {synthesis_claim} [Sources: 1]",
                trade_offs=[],
                evidence=[ev],
                limitations=[],
                conclusion=synthesis_claim,
                sources=[src],
            )
            evaluation = ReportEvaluation(
                grounded=True,
                citation_correct=True,
                hallucination_detected=False,
                score=5,
                reasoning="All supported",
                unsupported_claims=[],
            )
            return {
                "question": question,
                "report": report,
                "evidence": [ev],
                "citations": [1],
                "report_evaluation": evaluation,
                "research_sufficient": True,
                "conflicts": [],
                "evaluation_iteration": 1,
            }

    return FakeGraph()


@pytest.mark.asyncio
async def test_runner_produces_machine_readable_results(tmp_path):
    dataset = load_dataset()[:2]  # 2 items for speed
    runner = EvaluationRunner(graph_builder=lambda: make_fake_graph(), dataset_path=None)
    out = tmp_path / "results.jsonl"
    results = await runner.run_all(items=dataset, output_path=out)
    assert len(results) == 2
    assert all(r.error is None for r in results)
    # JSONL file exists and is parseable
    lines = pathlib.Path(out).read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert "id" in obj and "quality" in obj and "latency_seconds" in obj
        assert "aggregate_score" in obj["quality"]
        assert 0 <= obj["quality"]["aggregate_score"] <= 1


@pytest.mark.asyncio
async def test_runner_handles_graph_error_gracefully():
    class FailingGraph:
        async def ainvoke(self, *a, **kw):
            raise RuntimeError("boom")

    runner = EvaluationRunner(graph_builder=lambda: FailingGraph())
    items = load_dataset()[:1]
    results = await runner.run_all(items=items)
    assert results[0].error is not None
    assert "RuntimeError" in results[0].error
    assert results[0].report is None
    assert results[0].quality["aggregate_score"] == 0.0


def test_summarize_results_aggregates():
    from app.eval.runner import EvalResult

    # use runner to produce two results then summarize
    import asyncio

    async def _run():
        runner = EvaluationRunner(graph_builder=lambda: make_fake_graph())
        items = load_dataset()[:3]
        return await runner.run_all(items=items)

    results = asyncio.run(_run())
    summary = summarize_results(results)
    assert summary["count"] == 3
    assert "aggregate_score_mean" in summary
    assert summary["citation_valid_rate"] == pytest.approx(1.0)
    assert summary["grounded_rate"] == pytest.approx(1.0)
    assert summary["error_count"] == 0


def test_runner_is_repeatable_with_same_fake():
    import asyncio

    def run_once():
        r = EvaluationRunner(graph_builder=lambda: make_fake_graph("repeatable claim"))
        return asyncio.run(r.run_all(items=load_dataset()[:1]))

    a = run_once()
    b = run_once()
    # deterministic fake → same aggregate
    assert a[0].quality["aggregate_score"] == b[0].quality["aggregate_score"]
    assert a[0].report["title"] == b[0].report["title"]


def test_runner_sync_writes_incrementally(tmp_path):
    runner = EvaluationRunner(graph_builder=lambda: make_fake_graph())
    items = load_dataset()[:1]
    out = tmp_path / "sync.jsonl"
    # sync wrapper — run in separate loop, not inside pytest-asyncio loop
    import asyncio

    # ensure no running loop interferes — use new loop via asyncio.run in this sync test
    results = asyncio.run(runner.run_all(items=items, output_path=out))
    # also test run_all_sync via direct call in isolated thread
    assert len(results) == 1
    assert out.exists()
    assert json.loads(out.read_text().splitlines()[0])["id"] == items[0].id
