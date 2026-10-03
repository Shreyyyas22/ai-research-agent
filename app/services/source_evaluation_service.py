from app.llm.base import LLMProvider
from app.schemas.research import Evidence, SourceEvaluation


SOURCE_EVALUATION_SYSTEM_PROMPT = """
You are a source evaluation component for a research agent.

Your job is to evaluate whether the provided evidence is sufficient
to answer the research question.

You must also identify meaningful contradictions between evidence items.

Sufficiency rules:
- Mark sufficient=true only when the evidence adequately covers the
  research question.
- If important information is missing, mark sufficient=false.
- Explain why the evidence is or is not sufficient.
- List the important missing information when evidence is insufficient.

Conflict rules:
- Identify genuine contradictions between evidence claims.
- Do not treat differences in wording as contradictions.
- Do not resolve a conflict by simply choosing one source.
- Provide a possible explanation for the disagreement.
- Assign confidence as low, medium, or high.
- If there are no meaningful conflicts, return an empty conflicts list.

Use only the supplied research question and evidence.
Do not introduce outside knowledge.
""".strip()


class SourceEvaluationService:
    """Evaluate evidence sufficiency and detect conflicts."""

    async def evaluate(
        self,
        question: str,
        evidence: list[Evidence],
        llm_provider: LLMProvider,
    ) -> SourceEvaluation:
        """Evaluate whether evidence is sufficient and detect conflicts."""

        if not question.strip():
            raise ValueError("Research question cannot be empty.")

        if not evidence:
            return SourceEvaluation(
                sufficiency={
                    "sufficient": False,
                    "reasoning": "No evidence was collected.",
                    "missing_information": [
                        "Relevant supporting evidence",
                    ],
                },
                conflicts=[],
            )

        evidence_text = "\n\n".join(
            (
                f"Evidence {index}:\n"
                f"Source: {item.source.title}\n"
                f"URL: {item.source.url}\n"
                f"Claim: {item.claim}\n"
                f"Excerpt: {item.excerpt}"
            )
            for index, item in enumerate(evidence, start=1)
        )

        messages = [
            {
                "role": "system",
                "content": SOURCE_EVALUATION_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Research question:\n{question.strip()}\n\n"
                    f"Collected evidence:\n{evidence_text}"
                ),
            },
        ]

        return await llm_provider.generate_structured(
            messages=messages,
            response_model=SourceEvaluation,
        )