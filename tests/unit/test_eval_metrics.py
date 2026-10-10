import pytest

from app.eval.metrics import compute_quality_metrics
from app.schemas.research import (
    Evidence,
    ReportEvaluation,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


def make_evidence():
    src = Source(title="PostgreSQL Docs", url="https://example.com/pg")
    return [
        Evidence(source=src, claim="PostgreSQL supports vector search", excerpt="PostgreSQL supports vector search via pgvector"),
        Evidence(source=src, claim="pgvector integrates with relational data", excerpt="pgvector integrates with relational data and supports HNSW"),
    ]


def make_report(citation_ids=(1,)):
    ev = make_evidence()
    return ResearchReport(
        title="Research Report: test",
        executive_summary="PostgreSQL supports vector search via pgvector. Keyword: HNSW.",
        key_findings=[SynthesizedClaim(claim="PostgreSQL supports vector search", citation_ids=list(citation_ids))],
        detailed_analysis="1. PostgreSQL supports vector search [Sources: 1]",
        trade_offs=[],
        evidence=ev,
        limitations=[],
        conclusion="PostgreSQL supports vector search",
        sources=[e.source for e in ev],
    )


def make_eval(grounded=True, citation_correct=True, hallucination=False, score=5):
    return ReportEvaluation(
        grounded=grounded,
        citation_correct=citation_correct,
        hallucination_detected=hallucination,
        score=score,
        reasoning="ok",
        unsupported_claims=[] if grounded else ["unsupported"],
    )


def test_citation_metrics_valid_and_invalid():
    ev = make_evidence()
    report_ok = make_report(citation_ids=(1,))
    q = compute_quality_metrics(
        report=report_ok, evidence=ev, question="Does PostgreSQL support vector search?",
        expected_claims=["PostgreSQL supports vector search"], must_contain_keywords=["PostgreSQL"],
        min_evidence=1, report_evaluation=make_eval(),
    )
    assert q.citation.citation_valid is True
    assert q.citation.citation_ids_in_range is True
    assert q.citation.citation_correct_llm is True

    report_bad = make_report(citation_ids=(99,))
    q2 = compute_quality_metrics(
        report=report_bad, evidence=ev, question="Does PostgreSQL support vector search?",
        expected_claims=["PostgreSQL supports vector search"], must_contain_keywords=["PostgreSQL"],
        min_evidence=1, report_evaluation=make_eval(citation_correct=False),
    )
    assert q2.citation.citation_valid is False
    assert q2.citation.citation_ids_in_range is False
    assert "Invalid citation IDs" in (q2.citation.error or "")


def test_coverage_metrics_recall():
    ev = make_evidence()
    report = make_report()
    q = compute_quality_metrics(
        report=report, evidence=ev, question="Does PostgreSQL support vector search?",
        expected_claims=["PostgreSQL supports vector search", "missing claim xyz"], must_contain_keywords=["PostgreSQL"],
        min_evidence=1, report_evaluation=make_eval(),
    )
    # one of two expected claims found → 0.5
    assert q.coverage.expected_claims_recall == pytest.approx(0.5)
    assert q.coverage.evidence_count == 2
    assert q.coverage.min_evidence_met is True


def test_grounding_metrics_and_score_normalization():
    ev = make_evidence()
    report = make_report()
    q = compute_quality_metrics(
        report=report, evidence=ev, question="q",
        expected_claims=[], must_contain_keywords=[],
        min_evidence=1, report_evaluation=make_eval(grounded=True, hallucination=False, score=5),
    )
    assert q.grounding.grounded is True
    assert q.grounding.hallucination_detected is False
    assert q.grounding.score == 5
    assert q.grounding.score_normalized == pytest.approx(1.0)

    q2 = compute_quality_metrics(
        report=report, evidence=ev, question="q",
        expected_claims=[], must_contain_keywords=[],
        min_evidence=1, report_evaluation=make_eval(grounded=False, hallucination=True, score=1),
    )
    assert q2.grounding.hallucination_detected is True
    assert q2.grounding.score_normalized == pytest.approx(0.0)


def test_relevance_metrics_keyword_recall():
    ev = make_evidence()
    report = make_report()
    q = compute_quality_metrics(
        report=report, evidence=ev, question="Does PostgreSQL support vector search?",
        expected_claims=[], must_contain_keywords=["PostgreSQL", "vector", "missingkw"],
        min_evidence=1, report_evaluation=make_eval(),
    )
    # 2 of 3 keywords present → 0.666
    assert q.relevance.must_keywords_recall == pytest.approx(2 / 3)
    assert q.relevance.claim_count == 1


def test_aggregate_score_between_0_and_1():
    ev = make_evidence()
    report = make_report()
    q = compute_quality_metrics(
        report=report, evidence=ev, question="Does PostgreSQL support vector search?",
        expected_claims=["PostgreSQL supports vector search"], must_contain_keywords=["PostgreSQL"],
        min_evidence=1, report_evaluation=make_eval(score=5),
    )
    assert 0 <= q.aggregate_score <= 1
    # perfect case should be 1.0
    assert q.aggregate_score == pytest.approx(1.0)

    # hallucinated report → penalty
    q_bad = compute_quality_metrics(
        report=make_report(citation_ids=(99,)), evidence=ev, question="q",
        expected_claims=["missing"], must_contain_keywords=["missingkw"],
        min_evidence=10, report_evaluation=make_eval(grounded=False, hallucination=True, score=1),
        sufficiency=False,
    )
    assert q_bad.aggregate_score < 0.5


def test_no_evaluation_still_computes_deterministic():
    ev = make_evidence()
    report = make_report()
    q = compute_quality_metrics(
        report=report, evidence=ev, question="q",
        expected_claims=["PostgreSQL supports vector search"], must_contain_keywords=["PostgreSQL"],
        min_evidence=1, report_evaluation=None,
    )
    assert q.grounding.grounded is None
    assert q.citation.citation_correct_llm is None
    # deterministic parts still valid
    assert q.citation.citation_valid is True
    assert q.coverage.expected_claims_recall == pytest.approx(1.0)
