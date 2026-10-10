from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.schemas.research import Evidence, ResearchReport, ReportEvaluation
from app.services.citation_service import CitationService, CitationValidationError


@dataclass(frozen=True)
class CitationMetrics:
    """Citation correctness — deterministic + LLM."""

    citation_valid: bool  # CitationService.validate passed
    citation_ids_in_range: bool  # all ids ∈ [1..len(evidence)]
    citation_count: int
    citation_ids_unique: bool
    citation_correct_llm: bool | None  # from ReportEvaluation
    error: str | None = None


@dataclass(frozen=True)
class CoverageMetrics:
    """Evidence coverage — sufficiency and expected-claim recall."""

    sufficient: bool | None  # from SourceEvaluation if available else heuristic
    evidence_count: int
    min_evidence_met: bool
    expected_claims_recall: float  # 0..1 fraction of expected_claims found in report
    missing_information: list[str]


@dataclass(frozen=True)
class GroundingMetrics:
    """Factual grounding — hallucination detection."""

    grounded: bool | None
    hallucination_detected: bool | None
    unsupported_claims_count: int
    score: int | None  # 1..5 from ReportEvaluation
    score_normalized: float | None  # 0..1


@dataclass(frozen=True)
class RelevanceMetrics:
    """Answer relevance — question/keyword coverage."""

    must_keywords_recall: float  # fraction of must_contain_keywords found
    question_keywords_in_report: bool
    claim_count: int


@dataclass(frozen=True)
class QualityMetrics:
    citation: CitationMetrics
    coverage: CoverageMetrics
    grounding: GroundingMetrics
    relevance: RelevanceMetrics
    # aggregate quality 0..1 for ranking runs
    aggregate_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "citation": asdict(self.citation),
            "coverage": asdict(self.coverage),
            "grounding": asdict(self.grounding),
            "relevance": asdict(self.relevance),
            "aggregate_score": self.aggregate_score,
        }


def _normalize(text: str) -> str:
    return text.lower().strip()


def _claim_in_report(claim: str, report: ResearchReport) -> bool:
    """Deterministic substring check across report fields."""
    haystack = " ".join(
        [
            report.title,
            report.executive_summary,
            report.detailed_analysis,
            report.conclusion,
            " ".join(c.claim for c in report.key_findings),
        ]
    ).lower()
    return _normalize(claim) in haystack or any(_normalize(claim) in _normalize(c.claim) for c in report.key_findings)


def _keywords_recall(keywords: list[str], report: ResearchReport) -> float:
    if not keywords:
        return 1.0
    haystack = " ".join(
        [report.executive_summary, report.detailed_analysis, report.conclusion]
        + [c.claim for c in report.key_findings]
    ).lower()
    hits = sum(1 for k in keywords if _normalize(k) in haystack)
    return hits / len(keywords)


def compute_citation_metrics(
    report: ResearchReport,
    evidence: list[Evidence],
    report_evaluation: ReportEvaluation | None,
) -> CitationMetrics:
    citation_ids: list[int] = []
    for c in report.key_findings:
        citation_ids.extend(c.citation_ids)
    unique = len(citation_ids) == len(set(citation_ids)) if citation_ids else True
    valid_range = all(1 <= cid <= len(evidence) for cid in citation_ids) if evidence else not citation_ids
    # reuse existing CitationService — do not duplicate logic
    svc = CitationService()
    valid_ids = set(range(1, len(evidence) + 1)) if evidence else set()
    citation_valid = True
    error: str | None = None
    try:
        # build SynthesisResult shim from report findings for validation
        from app.schemas.research import SynthesisResult

        svc.validate(SynthesisResult(claims=report.key_findings), valid_ids)
    except CitationValidationError as exc:
        citation_valid = False
        error = str(exc)
    except Exception as exc:  # pragma: no cover
        citation_valid = False
        error = str(exc)

    return CitationMetrics(
        citation_valid=citation_valid,
        citation_ids_in_range=valid_range,
        citation_count=len(citation_ids),
        citation_ids_unique=unique,
        citation_correct_llm=report_evaluation.citation_correct if report_evaluation else None,
        error=error,
    )


def compute_coverage_metrics(
    evidence: list[Evidence],
    report: ResearchReport,
    expected_claims: list[str],
    min_evidence: int,
    sufficiency: bool | None = None,
    missing_information: list[str] | None = None,
) -> CoverageMetrics:
    if expected_claims:
        hits = sum(1 for ec in expected_claims if _claim_in_report(ec, report))
        recall = hits / len(expected_claims)
    else:
        recall = 1.0
    return CoverageMetrics(
        sufficient=sufficiency,
        evidence_count=len(evidence),
        min_evidence_met=len(evidence) >= min_evidence,
        expected_claims_recall=recall,
        missing_information=missing_information or [],
    )


def compute_grounding_metrics(
    report_evaluation: ReportEvaluation | None,
) -> GroundingMetrics:
    if report_evaluation is None:
        return GroundingMetrics(
            grounded=None,
            hallucination_detected=None,
            unsupported_claims_count=0,
            score=None,
            score_normalized=None,
        )
    return GroundingMetrics(
        grounded=report_evaluation.grounded,
        hallucination_detected=report_evaluation.hallucination_detected,
        unsupported_claims_count=len(report_evaluation.unsupported_claims),
        score=report_evaluation.score,
        score_normalized=(report_evaluation.score - 1) / 4 if report_evaluation.score else None,
    )


def compute_relevance_metrics(
    report: ResearchReport,
    question: str,
    must_keywords: list[str],
) -> RelevanceMetrics:
    recall = _keywords_recall(must_keywords, report)
    q_words = {w.lower() for w in question.split() if len(w) > 3}
    haystack = (report.executive_summary + " " + report.conclusion).lower()
    q_in_report = any(w in haystack for w in q_words) if q_words else True
    return RelevanceMetrics(
        must_keywords_recall=recall,
        question_keywords_in_report=q_in_report,
        claim_count=len(report.key_findings),
    )


def compute_quality_metrics(
    *,
    report: ResearchReport,
    evidence: list[Evidence],
    question: str,
    expected_claims: list[str],
    must_contain_keywords: list[str],
    min_evidence: int,
    report_evaluation: ReportEvaluation | None = None,
    sufficiency: bool | None = None,
    missing_information: list[str] | None = None,
) -> QualityMetrics:
    """Compose the four quality pillars; reuses existing evaluators."""
    citation = compute_citation_metrics(report, evidence, report_evaluation)
    coverage = compute_coverage_metrics(evidence, report, expected_claims, min_evidence, sufficiency, missing_information)
    grounding = compute_grounding_metrics(report_evaluation)
    relevance = compute_relevance_metrics(report, question, must_contain_keywords)

    # aggregate 0..1: weighted mean of deterministic signals + LLM score
    parts: list[float] = []
    parts.append(float(citation.citation_valid))
    parts.append(coverage.expected_claims_recall)
    parts.append(relevance.must_keywords_recall)
    if grounding.score_normalized is not None:
        parts.append(grounding.score_normalized)
    # hallucination penalty
    if grounding.hallucination_detected is True:
        parts.append(0.0)
    elif grounding.hallucination_detected is False:
        parts.append(1.0)
    # sufficiency
    if coverage.sufficient is not None:
        parts.append(1.0 if coverage.sufficient else 0.0)

    aggregate = sum(parts) / len(parts) if parts else 0.0

    return QualityMetrics(
        citation=citation,
        coverage=coverage,
        grounding=grounding,
        relevance=relevance,
        aggregate_score=round(aggregate, 4),
    )
