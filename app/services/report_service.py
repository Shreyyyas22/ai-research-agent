from app.schemas.research import (
    Conflict,
    Evidence,
    ResearchReport,
    Source,
    SynthesisResult,
)


class ReportService:
    """Build a structured research report from validated research outputs."""

    def build_report(
        self,
        question: str,
        synthesis: SynthesisResult,
        evidence: list[Evidence],
        sources: list[Source],
        conflicts: list[Conflict] | None = None,
    ) -> ResearchReport:
        if not question.strip():
            raise ValueError("Research question cannot be empty.")

        if not synthesis.claims:
            raise ValueError("Cannot build a report without synthesized claims.")

        if not sources:
            raise ValueError("Cannot build a report without sources.")

        conflicts = conflicts or []

        title = f"Research Report: {question.strip()}"

        executive_summary = self._build_executive_summary(
            synthesis=synthesis,
            conflicts=conflicts,
        )

        detailed_analysis = self._build_detailed_analysis(
            synthesis=synthesis,
            conflicts=conflicts,
        )

        trade_offs = self._extract_trade_offs(conflicts)

        limitations = self._build_limitations(
            evidence=evidence,
            conflicts=conflicts,
        )

        conclusion = self._build_conclusion(synthesis)

        return ResearchReport(
            title=title,
            executive_summary=executive_summary,
            key_findings=synthesis.claims,
            detailed_analysis=detailed_analysis,
            trade_offs=trade_offs,
            evidence=evidence,
            limitations=limitations,
            conclusion=conclusion,
            sources=sources,
        )

    def _build_executive_summary(
        self,
        synthesis: SynthesisResult,
        conflicts: list[Conflict],
    ) -> str:
        findings = " ".join(
            claim.claim for claim in synthesis.claims[:5]
        )

        if conflicts:
            return (
                f"The research identified the following key findings: {findings} "
                f"The evidence also contains {len(conflicts)} identified conflict(s) "
                "that should be considered when interpreting the findings."
            )

        return f"The research identified the following key findings: {findings}"

    def _build_detailed_analysis(
        self,
        synthesis: SynthesisResult,
        conflicts: list[Conflict],
    ) -> str:
        sections: list[str] = []

        for index, claim in enumerate(synthesis.claims, start=1):
            citation_text = ", ".join(
                str(citation_id)
                for citation_id in claim.citation_ids
            )

            sections.append(
                f"{index}. {claim.claim} "
                f"[Sources: {citation_text}]"
            )

        if conflicts:
            conflict_text = "\n".join(
                (
                    f"Conflict {index}: {conflict.claim_a} "
                    f"vs. {conflict.claim_b}. "
                    f"Possible explanation: "
                    f"{conflict.possible_explanation} "
                    f"(confidence: {conflict.confidence})."
                )
                for index, conflict in enumerate(conflicts, start=1)
            )

            sections.append(
                "Conflicting Evidence:\n" + conflict_text
            )

        return "\n\n".join(sections)

    def _extract_trade_offs(
        self,
        conflicts: list[Conflict],
    ) -> list[str]:
        return [
            (
                f"{conflict.claim_a} vs. {conflict.claim_b}: "
                f"{conflict.possible_explanation}"
            )
            for conflict in conflicts
        ]

    def _build_limitations(
        self,
        evidence: list[Evidence],
        conflicts: list[Conflict],
    ) -> list[str]:
        limitations: list[str] = []

        if not evidence:
            limitations.append("No evidence was collected.")

        if conflicts:
            limitations.append(
                "Some evidence contains unresolved conflicts."
            )

        return limitations

    def _build_conclusion(
        self,
        synthesis: SynthesisResult,
    ) -> str:
        return " ".join(
            claim.claim for claim in synthesis.claims
        )