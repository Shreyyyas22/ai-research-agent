from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, asdict
from typing import Any

from app.eval.runner import summarize_results


@dataclass(frozen=True)
class RunSummary:
    name: str
    summary: dict[str, Any]
    results: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "summary": self.summary, "results": self.results}


@dataclass(frozen=True)
class ComparisonReport:
    runs: list[RunSummary]
    comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"runs": [r.to_dict() for r in self.runs], "comparison": self.comparison}

    def to_markdown(self) -> str:
        lines: list[str] = ["# Evaluation Comparison Report", ""]
        # table header
        headers = ["Metric", *[r.name for r in self.runs]]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        metrics = [
            ("aggregate_score_mean", "Aggregate Score"),
            ("grounded_rate", "Grounded Rate"),
            ("hallucination_rate", "Hallucination Rate"),
            ("citation_valid_rate", "Citation Valid Rate"),
            ("expected_claims_recall_mean", "Claims Recall"),
            ("must_keywords_recall_mean", "Keyword Recall"),
            ("report_score_mean", "LLM Score (1-5)"),
            ("latency_mean_seconds", "Latency (s)"),
            ("error_count", "Errors"),
        ]
        for key, label in metrics:
            row = [label] + [str(r.summary.get(key, "n/a")) for r in self.runs]
            lines.append("| " + " | ".join(row) + " |")
        # deltas
        if len(self.runs) >= 2:
            lines.append("")
            lines.append("## Deltas (last - first)")
            first = self.runs[0].summary
            last = self.runs[-1].summary
            for key, label in metrics:
                try:
                    delta = round(float(last.get(key, 0)) - float(first.get(key, 0)), 4)
                    sign = "+" if delta > 0 else ""
                    lines.append(f"- {label}: {sign}{delta}")
                except Exception:
                    lines.append(f"- {label}: n/a")
        # per-category breakdown
        lines.append("")
        lines.append("## Per-Category Breakdown")
        for run in self.runs:
            lines.append(f"### {run.name}")
            # group by category
            by_cat: dict[str, list[dict[str, Any]]] = {}
            for r in run.results:
                by_cat.setdefault(r.get("category", "unknown"), []).append(r)
            for cat, items in sorted(by_cat.items()):
                agg = sum(i["quality"]["aggregate_score"] for i in items) / len(items) if items else 0
                grounded = sum(1 for i in items if i["quality"]["grounding"]["grounded"] is True)
                lines.append(f"- {cat}: n={len(items)}, agg={agg:.3f}, grounded={grounded}/{len(items)}")
        return "\n".join(lines)


def load_results_file(path: str | pathlib.Path) -> list[dict[str, Any]]:
    p = pathlib.Path(path)
    results: list[dict[str, Any]] = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        results.append(json.loads(line))
    return results


def generate_comparison_report(
    run_files: dict[str, str | pathlib.Path],
    output_json: str | pathlib.Path | None = None,
    output_md: str | pathlib.Path | None = None,
) -> ComparisonReport:
    """Compare quality across runs from JSONL files; machine-readable + markdown."""
    runs: list[RunSummary] = []
    for name, path in run_files.items():
        results = load_results_file(path)
        summary = summarize_results(results)
        runs.append(RunSummary(name=name, summary=summary, results=results))

    # comparison deltas
    comparison: dict[str, Any] = {}
    if len(runs) >= 2:
        keys = [
            "aggregate_score_mean",
            "grounded_rate",
            "citation_valid_rate",
            "expected_claims_recall_mean",
            "report_score_mean",
        ]
        for k in keys:
            vals = [r.summary.get(k, 0) for r in runs]
            comparison[k] = {
                "first": vals[0],
                "last": vals[-1],
                "delta": round(float(vals[-1]) - float(vals[0]), 4),
                "all": vals,
            }

    report = ComparisonReport(runs=runs, comparison=comparison)
    if output_json is not None:
        p = pathlib.Path(output_json)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report.to_dict(), indent=2))
    if output_md is not None:
        p = pathlib.Path(output_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(report.to_markdown())
    return report
