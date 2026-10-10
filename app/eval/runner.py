from __future__ import annotations

import json
import pathlib
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Callable, Awaitable

from app.eval.dataset import EvaluationItem, load_dataset
from app.eval.metrics import QualityMetrics, compute_quality_metrics
from app.schemas.research import Evidence, ResearchReport


@dataclass(frozen=True)
class EvalResult:
    """Machine-readable per-item result."""

    id: str
    question: str
    category: str
    difficulty: str
    report: dict[str, Any] | None
    evidence_count: int
    citation_count: int
    quality: dict[str, Any]
    latency_seconds: float
    error: str | None
    trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


GraphBuilder = Callable[[], Any]  # returns object with async ainvoke(input)->dict


class EvaluationRunner:
    """Repeatable evaluation — runs each dataset item through the graph and reuses existing evaluators."""

    def __init__(
        self,
        graph_builder: GraphBuilder,
        dataset_path: str | pathlib.Path | None = None,
    ) -> None:
        self.graph_builder = graph_builder
        self.dataset_path = dataset_path

    async def run_item(self, item: EvaluationItem) -> EvalResult:
        start = time.perf_counter()
        error: str | None = None
        report: ResearchReport | None = None
        evidence: list[Evidence] = []
        report_evaluation: Any = None
        source_evaluation: Any = None
        graph = self.graph_builder()
        # each item gets isolated run_id/trace_id
        run_id = f"eval-{item.id}-{uuid.uuid4().hex[:8]}"
        trace = {"run_id": run_id}
        try:
            result: dict[str, Any] = await graph.ainvoke({"question": item.question, "run_id": run_id})
            report = result.get("report")
            evidence = result.get("evidence") or []
            report_evaluation = result.get("report_evaluation")
            # source evaluation from graph state if present
            suff = result.get("research_sufficient")
            conflicts = result.get("conflicts") or []
            # try to get source_evaluation if graph exposed it via research_service
            # fallback: sufficiency from result flag
            trace.update(
                {
                    "research_sufficient": suff,
                    "conflicts_count": len(conflicts),
                    "citations": result.get("citations"),
                    "evaluation_iteration": result.get("evaluation_iteration"),
                }
            )
            # build quality metrics reusing existing services
            if report is not None:
                # extract sufficiency/missing from result if available
                suff_bool = suff if isinstance(suff, bool) else None
                quality = compute_quality_metrics(
                    report=report,
                    evidence=evidence,
                    question=item.question,
                    expected_claims=item.expected_claims,
                    must_contain_keywords=item.must_contain_keywords,
                    min_evidence=item.min_evidence,
                    report_evaluation=report_evaluation,
                    sufficiency=suff_bool,
                    missing_information=None,
                )
            else:
                # no report → zero quality
                from app.eval.metrics import CoverageMetrics, CitationMetrics, GroundingMetrics, RelevanceMetrics, QualityMetrics

                quality = QualityMetrics(
                    citation=CitationMetrics(False, False, 0, True, None, error="no report"),
                    coverage=CoverageMetrics(None, 0, False, 0.0, []),
                    grounding=GroundingMetrics(None, None, 0, None, None),
                    relevance=RelevanceMetrics(0.0, False, 0),
                    aggregate_score=0.0,
                )
        except Exception as exc:  # pragma: no cover
            error = f"{type(exc).__name__}: {exc}"
            # still compute zero quality
            from app.eval.metrics import CitationMetrics, CoverageMetrics, GroundingMetrics, QualityMetrics, RelevanceMetrics

            quality = QualityMetrics(
                citation=CitationMetrics(False, False, 0, True, None, error=error),
                coverage=CoverageMetrics(None, 0, False, 0.0, []),
                grounding=GroundingMetrics(None, None, 0, None, None),
                relevance=RelevanceMetrics(0.0, False, 0),
                aggregate_score=0.0,
            )
            report = None
            evidence = []

        latency = time.perf_counter() - start
        return EvalResult(
            id=item.id,
            question=item.question,
            category=item.category,
            difficulty=item.difficulty,
            report=report.model_dump() if report else None,
            evidence_count=len(evidence),
            citation_count=len(report.key_findings) if report else 0,
            quality=quality.to_dict() if hasattr(quality, "to_dict") else quality,
            latency_seconds=round(latency, 4),
            error=error,
            trace=trace,
        )

    async def run_all(
        self,
        items: list[EvaluationItem] | None = None,
        output_path: str | pathlib.Path | None = None,
    ) -> list[EvalResult]:
        if items is None:
            items = load_dataset(self.dataset_path)
        results: list[EvalResult] = []
        for item in items:
            res = await self.run_item(item)
            results.append(res)
            if output_path is not None:
                # incremental JSONL for repeatability even if interrupted
                p = pathlib.Path(output_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open("a") as f:
                    f.write(json.dumps(res.to_dict()) + "\n")
        return results

    def run_all_sync(
        self,
        items: list[EvaluationItem] | None = None,
        output_path: str | pathlib.Path | None = None,
    ) -> list[EvalResult]:
        import asyncio

        # ensure file is clean for sync run
        if output_path is not None:
            pathlib.Path(output_path).write_text("")
        return asyncio.run(self.run_all(items, output_path))


def summarize_results(results: list[EvalResult] | list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate quality across a run for comparison."""
    # accept both EvalResult and dict
    dicts = [r if isinstance(r, dict) else r.to_dict() for r in results]
    if not dicts:
        return {"count": 0}
    def avg(key: str, sub: str | None = None):
        vals = []
        for d in dicts:
            q = d["quality"]
            if sub:
                # submetrics like coverage.expected_claims_recall
                parts = key.split(".")
                v = q
                for p in parts:
                    v = v.get(p, {}) if isinstance(v, dict) else None
                # need drilling
                continue
            else:
                vals.append(q.get(key, 0))
        return sum(vals)/len(vals) if vals else 0

    # explicit averages
    n = len(dicts)
    aggs = sum(d["quality"]["aggregate_score"] for d in dicts) / n
    grounded_rate = sum(1 for d in dicts if d["quality"]["grounding"]["grounded"] is True) / n
    halluc_rate = sum(1 for d in dicts if d["quality"]["grounding"]["hallucination_detected"] is True) / n
    citation_valid_rate = sum(1 for d in dicts if d["quality"]["citation"]["citation_valid"] is True) / n
    recall = sum(d["quality"]["coverage"]["expected_claims_recall"] for d in dicts) / n
    keyword_recall = sum(d["quality"]["relevance"]["must_keywords_recall"] for d in dicts) / n
    avg_score = sum(d["quality"]["grounding"]["score"] or 0 for d in dicts) / n
    avg_latency = sum(d["latency_seconds"] for d in dicts) / n
    errors = sum(1 for d in dicts if d["error"])
    return {
        "count": n,
        "aggregate_score_mean": round(aggs, 4),
        "grounded_rate": round(grounded_rate, 4),
        "hallucination_rate": round(halluc_rate, 4),
        "citation_valid_rate": round(citation_valid_rate, 4),
        "expected_claims_recall_mean": round(recall, 4),
        "must_keywords_recall_mean": round(keyword_recall, 4),
        "report_score_mean": round(avg_score, 4),
        "latency_mean_seconds": round(avg_latency, 4),
        "error_count": errors,
    }
