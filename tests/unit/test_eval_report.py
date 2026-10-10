import json
import pathlib

import pytest

from app.eval.dataset import load_dataset
from app.eval.report import generate_comparison_report, load_results_file
from app.eval.runner import EvaluationRunner
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


def make_graph_with_score(score: int, grounded: bool = True):
    class FakeGraph:
        async def ainvoke(self, input, **kwargs):
            q = input["question"]
            src = Source(title="T", url="https://example.com")
            ev = Evidence(source=src, claim="PostgreSQL supports vector search", excerpt="PostgreSQL supports vector search")
            report = ResearchReport(
                title=f"Report: {q}",
                executive_summary="PostgreSQL supports vector search",
                key_findings=[SynthesizedClaim(claim="PostgreSQL supports vector search", citation_ids=[1])],
                detailed_analysis="1. PostgreSQL supports vector search [Sources: 1]",
                trade_offs=[],
                evidence=[ev],
                limitations=[],
                conclusion="PostgreSQL supports vector search",
                sources=[src],
            )
            evaluation = ReportEvaluation(
                grounded=grounded,
                citation_correct=grounded,
                hallucination_detected=not grounded,
                score=score,
                reasoning="ok",
                unsupported_claims=[] if grounded else ["bad"],
            )
            return {"question": q, "report": report, "evidence": [ev], "citations": [1], "report_evaluation": evaluation, "research_sufficient": True, "conflicts": []}

    return FakeGraph()


@pytest.mark.asyncio
async def test_comparison_report_distinguishes_runs(tmp_path):
    items = load_dataset()[:2]
    # run A with score 5 (high quality)
    rA = EvaluationRunner(graph_builder=lambda: make_graph_with_score(5, True))
    # run B with score 2 (low quality)
    rB = EvaluationRunner(graph_builder=lambda: make_graph_with_score(2, False))

    fileA = tmp_path / "runA.jsonl"
    fileB = tmp_path / "runB.jsonl"
    await rA.run_all(items=items, output_path=fileA)
    await rB.run_all(items=items, output_path=fileB)

    out_json = tmp_path / "comparison.json"
    out_md = tmp_path / "comparison.md"
    report = generate_comparison_report(
        {"prompt_v1_high": fileA, "prompt_v2_low": fileB},
        output_json=out_json,
        output_md=out_md,
    )
    # structure
    assert len(report.runs) == 2
    assert report.runs[0].name == "prompt_v1_high"
    assert report.runs[1].name == "prompt_v2_low"
    assert "aggregate_score_mean" in report.runs[0].summary
    # deltas present
    assert "aggregate_score_mean" in report.comparison
    assert report.comparison["aggregate_score_mean"]["delta"] < 0  # high -> low drops
    # files written
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert "runs" in data and "comparison" in data
    assert out_md.exists()
    md = out_md.read_text()
    assert "# Evaluation Comparison Report" in md
    assert "prompt_v1_high" in md
    assert "prompt_v2_low" in md
    assert "Deltas" in md
    assert "Per-Category Breakdown" in md


def test_load_results_file_handles_empty_lines(tmp_path):
    p = tmp_path / "r.jsonl"
    p.write_text('{"a":1}\n\n{"a":2}\n')
    loaded = load_results_file(p)
    assert len(loaded) == 2


def test_generate_report_single_run_no_deltas(tmp_path):
    items = load_dataset()[:1]
    r = EvaluationRunner(graph_builder=lambda: make_graph_with_score(4, True))
    import asyncio

    results = asyncio.run(r.run_all(items=items))
    f = tmp_path / "single.jsonl"
    f.write_text("\n".join(json.dumps(r.to_dict()) for r in results))
    report = generate_comparison_report({"single": f})
    assert len(report.runs) == 1
    assert report.comparison == {}  # no delta with single run
    md = report.to_markdown()
    assert "Deltas" not in md
