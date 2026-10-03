import pytest

from app.schemas.research import (
    Conflict,
    Evidence,
    Source,
    SynthesisResult,
    SynthesizedClaim,
)
from app.services.report_service import ReportService


def make_source(title: str, url: str) -> Source:
    return Source(
        title=title,
        url=url,
    )


def make_evidence(source: Source, claim: str) -> Evidence:
    return Evidence(
        source=source,
        claim=claim,
        excerpt=f"Evidence supporting: {claim}",
    )


def make_synthesis() -> SynthesisResult:
    return SynthesisResult(
        claims=[
            SynthesizedClaim(
                claim="PostgreSQL supports vector search.",
                citation_ids=[1],
            ),
            SynthesizedClaim(
                claim="PostgreSQL can also support traditional relational workloads.",
                citation_ids=[2],
            ),
        ]
    )


def test_build_report():
    service = ReportService()

    source_1 = make_source(
        "PostgreSQL Documentation",
        "https://example.com/postgres",
    )
    source_2 = make_source(
        "Vector Search Article",
        "https://example.com/vector-search",
    )

    evidence = [
        make_evidence(
            source_1,
            "PostgreSQL supports vector search.",
        ),
        make_evidence(
            source_2,
            "PostgreSQL supports relational workloads.",
        ),
    ]

    report = service.build_report(
        question="What are the capabilities of PostgreSQL?",
        synthesis=make_synthesis(),
        evidence=evidence,
        sources=[source_1, source_2],
    )

    assert report.title == (
        "Research Report: What are the capabilities of PostgreSQL?"
    )

    assert len(report.key_findings) == 2
    assert report.key_findings[0].citation_ids == [1]

    assert len(report.evidence) == 2
    assert len(report.sources) == 2

    assert report.executive_summary
    assert report.detailed_analysis
    assert report.conclusion


def test_build_report_includes_conflicts():
    service = ReportService()

    source = make_source(
        "Example Source",
        "https://example.com",
    )

    evidence = [
        make_evidence(
            source,
            "Example claim.",
        )
    ]

    conflicts = [
        Conflict(
            claim_a="Source A says X.",
            claim_b="Source B says Y.",
            possible_explanation="Different methodologies.",
            confidence="medium",
        )
    ]

    report = service.build_report(
        question="Example research question",
        synthesis=make_synthesis(),
        evidence=evidence,
        sources=[source],
        conflicts=conflicts,
    )

    assert len(report.trade_offs) == 1
    assert "Different methodologies." in report.trade_offs[0]

    assert "unresolved conflicts" in report.limitations[0]

    assert "Conflicting Evidence" in report.detailed_analysis


def test_build_report_rejects_empty_question():
    service = ReportService()

    source = make_source(
        "Example Source",
        "https://example.com",
    )

    with pytest.raises(ValueError, match="Research question cannot be empty"):
        service.build_report(
            question="   ",
            synthesis=make_synthesis(),
            evidence=[],
            sources=[source],
        )




def test_build_report_rejects_empty_sources():
    service = ReportService()

    with pytest.raises(ValueError, match="without sources"):
        service.build_report(
            question="Example question",
            synthesis=make_synthesis(),
            evidence=[],
            sources=[],
        )