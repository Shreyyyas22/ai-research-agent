from app.schemas.research import ResearchReport


class MarkdownReportRenderer:
    """Render a ResearchReport as human-readable Markdown."""

    def render(self, report: ResearchReport) -> str:
        sections: list[str] = []

        sections.append(f"# {report.title}")

        sections.append(
            "## Executive Summary\n\n"
            f"{report.executive_summary}"
        )

        sections.append(
            "## Key Findings\n\n"
            + "\n".join(
                (
                    f"- {finding.claim} "
                    f"{self._format_citations(finding.citation_ids)}"
                )
                for finding in report.key_findings
            )
        )

        sections.append(
            "## Detailed Analysis\n\n"
            f"{report.detailed_analysis}"
        )

        if report.trade_offs:
            sections.append(
                "## Trade-offs\n\n"
                + "\n".join(
                    f"- {trade_off}" for trade_off in report.trade_offs
                )
            )

        if report.evidence:
            evidence_lines = []

            for index, evidence in enumerate(report.evidence, start=1):
                evidence_lines.append(
                    f"### Evidence {index}\n\n"
                    f"**Claim:** {evidence.claim}\n\n"
                    f"**Excerpt:** {evidence.excerpt}\n\n"
                    f"**Source:** {evidence.source.title} "
                    f"({evidence.source.url})"
                )

            sections.append(
                "## Evidence\n\n"
                + "\n\n".join(evidence_lines)
            )

        if report.limitations:
            sections.append(
                "## Limitations\n\n"
                + "\n".join(
                    f"- {limitation}"
                    for limitation in report.limitations
                )
            )

        sections.append(
            "## Conclusion\n\n"
            f"{report.conclusion}"
        )

        sections.append(
            "## Sources\n\n"
            + "\n".join(
                (
                    f"{index}. [{source.title}]({source.url})"
                )
                for index, source in enumerate(report.sources, start=1)
            )
        )

        return "\n\n".join(sections)

    def _format_citations(self, citation_ids: list[int]) -> str:
        return " ".join(
            f"[{citation_id}]"
            for citation_id in citation_ids
        )