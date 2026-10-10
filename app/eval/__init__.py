"""Evaluation dataset & quality metrics — reuses ReportEvaluator, CitationService, SourceEvaluation."""

from app.eval.dataset import EvaluationItem, load_dataset
from app.eval.metrics import (
    CitationMetrics,
    CoverageMetrics,
    GroundingMetrics,
    QualityMetrics,
    RelevanceMetrics,
    compute_quality_metrics,
)
from app.eval.report import ComparisonReport, generate_comparison_report
from app.eval.runner import EvalResult, EvaluationRunner

__all__ = [
    "CitationMetrics",
    "ComparisonReport",
    "CoverageMetrics",
    "EvalResult",
    "EvaluationItem",
    "EvaluationRunner",
    "GroundingMetrics",
    "QualityMetrics",
    "RelevanceMetrics",
    "compute_quality_metrics",
    "generate_comparison_report",
    "load_dataset",
]
