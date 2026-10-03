import pytest
from pydantic import ValidationError

from app.schemas.research import (
    Evidence,
    ResearchReport,
    Source,
    SynthesizedClaim,
)


def make_valid_report() -> ResearchReport:
    source = Source(
        title="Example Source",
        url="https://example.com",
    )

    evidence = Evidence(
        source=source,
        claim="Example claim",
        excerpt="Example supporting excerpt.",
    )

    finding = SynthesizedClaim(
        claim="Example finding",
        citation_ids=[1],
    )

    return ResearchReport(
        title="Example Research Report",
        executive_summary="This is the executive summary.",
        key_findings=[finding],
        detailed_analysis="This is the detailed analysis.",
        trade_offs=["Trade-off one"],
        evidence=[evidence],
        limitations=["Limited evidence"],
        conclusion="This is the conclusion.",
        sources=[source],
    )


def test_valid_research_report():
    report = make_valid_report()

    assert report.title == "Example Research Report"
    assert len(report.key_findings) == 1
    assert len(report.evidence) == 1
    assert len(report.sources) == 1


def test_research_report_requires_key_findings():
    with pytest.raises(ValidationError):
        ResearchReport(
            title="Example Research Report",
            executive_summary="Summary",
            key_findings=[],
            detailed_analysis="Analysis",
            conclusion="Conclusion",
            sources=[
                Source(
                    title="Example Source",
                    url="https://example.com",
                )
            ],
        )


def test_research_report_requires_sources():
    with pytest.raises(ValidationError):
        ResearchReport(
            title="Example Research Report",
            executive_summary="Summary",
            key_findings=[
                SynthesizedClaim(
                    claim="Example finding",
                    citation_ids=[1],
                )
            ],
            detailed_analysis="Analysis",
            conclusion="Conclusion",
            sources=[],
        )


def test_research_report_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ResearchReport(
            title="Example Research Report",
            executive_summary="Summary",
            key_findings=[
                SynthesizedClaim(
                    claim="Example finding",
                    citation_ids=[1],
                )
            ],
            detailed_analysis="Analysis",
            conclusion="Conclusion",
            sources=[
                Source(
                    title="Example Source",
                    url="https://example.com",
                )
            ],
            unexpected_field="not allowed",
        )