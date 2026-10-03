from app.schemas.research import (
    Evidence,
    ResearchReport,
    Source,
    SynthesizedClaim,
)
from app.services.report_renderer import MarkdownReportRenderer


def make_report() -> ResearchReport:
    source_1 = Source(
        title="PostgreSQL Documentation",
        url="https://example.com/postgres",
    )

    source_2 = Source(
        title="Vector Search Article",
        url="https://example.com/vector-search",
    )

    evidence = [
        Evidence(
            source=source_1,
            claim="PostgreSQL supports vector search.",
            excerpt="PostgreSQL can store and query vector data.",
        ),
        Evidence(
            source=source_2,
            claim="Vector search enables semantic retrieval.",
            excerpt="Vector similarity can retrieve semantically related content.",
        ),
    ]

    return ResearchReport(
        title="Research Report: PostgreSQL Vector Search",
        executive_summary="PostgreSQL can support vector search.",
        key_findings=[
            SynthesizedClaim(
                claim="PostgreSQL supports vector search.",
                citation_ids=[1],
            ),
            SynthesizedClaim(
                claim="Vector search enables semantic retrieval.",
                citation_ids=[2],
            ),
        ],
        detailed_analysis=(
            "PostgreSQL can store vector representations and "
            "perform similarity searches."
        ),
        trade_offs=[
            "Vector search introduces additional storage and computation."
        ],
        evidence=evidence,
        limitations=[
            "The analysis is based on the provided evidence."
        ],
        conclusion="PostgreSQL can be used for vector-based retrieval.",
        sources=[source_1, source_2],
    )


def test_render_contains_all_main_sections():
    renderer = MarkdownReportRenderer()

    markdown = renderer.render(make_report())

    assert "# Research Report: PostgreSQL Vector Search" in markdown
    assert "## Executive Summary" in markdown
    assert "## Key Findings" in markdown
    assert "## Detailed Analysis" in markdown
    assert "## Trade-offs" in markdown
    assert "## Evidence" in markdown
    assert "## Limitations" in markdown
    assert "## Conclusion" in markdown
    assert "## Sources" in markdown


def test_render_preserves_citation_ids():
    renderer = MarkdownReportRenderer()

    markdown = renderer.render(make_report())

    assert "PostgreSQL supports vector search. [1]" in markdown
    assert "Vector search enables semantic retrieval. [2]" in markdown


def test_render_includes_evidence():
    renderer = MarkdownReportRenderer()

    markdown = renderer.render(make_report())

    assert "### Evidence 1" in markdown
    assert "**Claim:** PostgreSQL supports vector search." in markdown
    assert "**Excerpt:** PostgreSQL can store and query vector data." in markdown
    assert "**Source:** PostgreSQL Documentation" in markdown


def test_render_includes_markdown_source_links():
    renderer = MarkdownReportRenderer()

    markdown = renderer.render(make_report())

    assert "[PostgreSQL Documentation](https://example.com/postgres)" in markdown
    assert "[Vector Search Article](https://example.com/vector-search)" in markdown


def test_render_omits_empty_optional_sections():
    renderer = MarkdownReportRenderer()

    report = make_report().model_copy(
        update={
            "trade_offs": [],
            "limitations": [],
        }
    )

    markdown = renderer.render(report)

    assert "## Trade-offs" not in markdown
    assert "## Limitations" not in markdown