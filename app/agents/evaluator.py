from app.llm.base import LLMProvider
from app.schemas.research import Evidence, ReportEvaluation, ResearchReport


EVALUATOR_SYSTEM_PROMPT = """
You are a report evaluation component for a research agent.

Your job is to evaluate whether a generated research report is grounded
in the supplied research evidence.

Evaluate the report using ONLY the supplied question, report, and evidence.

Definitions:

- Groundedness:
  A factual claim in the report is supported by the supplied evidence.

- Hallucination:
  A factual claim appears in the report but cannot be supported by the
  supplied evidence.

- Citation correctness:
  The cited evidence actually supports the claim it is attached to.
  A citation is not correct merely because the citation ID exists.

Rules:

- Do not use outside knowledge.
- Do not assume a claim is true if it is not supported by the evidence.
- Check every important factual claim in the report.
- Check that citation IDs refer to the correct evidence items.
- If a claim is unsupported, include it in unsupported_claims.
- If an important unsupported factual claim exists, hallucination_detected
  should be true.
- If citations do not support their associated claims, citation_correct
  should be false.
- grounded should be false when important factual claims are unsupported.
- Score the report from 1 to 5 based on how well it is grounded in the
  supplied evidence.
- The score is an application-level evaluation and is not a scientifically
  calibrated metric.
- Do not fabricate evidence, citations, or reasoning.

Return only the required structured evaluation.
""".strip()


class ReportEvaluator:
    """Evaluate a generated research report against collected evidence."""

    async def evaluate(
        self,
        question: str,
        report: ResearchReport,
        evidence: list[Evidence],
        llm_provider: LLMProvider,
    ) -> ReportEvaluation:
        if not question.strip():
            raise ValueError("Research question cannot be empty.")

        if not evidence:
            raise ValueError("Cannot evaluate a report without evidence.")

        evidence_text = "\n\n".join(
            (
                f"Evidence ID: {index}\n"
                f"Source title: {item.source.title}\n"
                f"Source URL: {item.source.url}\n"
                f"Claim: {item.claim}\n"
                f"Excerpt: {item.excerpt}"
            )
            for index, item in enumerate(evidence, start=1)
        )

        report_text = (
            f"Title:\n{report.title}\n\n"
            f"Executive Summary:\n{report.executive_summary}\n\n"
            f"Key Findings:\n"
            + "\n".join(
                (
                    f"- Claim: {finding.claim}\n"
                    f"  Citation IDs: {finding.citation_ids}"
                )
                for finding in report.key_findings
            )
            + f"\n\nDetailed Analysis:\n{report.detailed_analysis}\n\n"
            f"Conclusion:\n{report.conclusion}"
        )

        messages = [
            {
                "role": "system",
                "content": EVALUATOR_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Research question:\n{question.strip()}\n\n"
                    f"Generated report:\n{report_text}\n\n"
                    f"Supplied evidence:\n{evidence_text}\n\n"
                    "Evaluate the report for groundedness, citation "
                    "correctness, and hallucination."
                ),
            },
        ]

        return await llm_provider.generate_structured(
            messages=messages,
            response_model=ReportEvaluation,
        )