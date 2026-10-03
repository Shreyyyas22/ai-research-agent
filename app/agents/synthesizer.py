from app.llm.base import LLMProvider
from app.schemas.research import (
    Conflict,
    Evidence,
    SynthesisResult,
)


SYNTHESIZER_SYSTEM_PROMPT = """
You are a research synthesis component for a research agent.

Your job is to synthesize a clear answer from the provided research evidence.

Rules:
- Use only the supplied evidence.
- Do not introduce outside knowledge.
- Every factual claim must be supported by one or more provided sources.
- Every claim must include citation IDs.
- Citation IDs must refer only to the provided source IDs.
- Do not invent citation IDs.
- Preserve meaningful conflicts instead of silently choosing one side.
- If sources disagree, clearly represent the disagreement.
- Do not fabricate evidence or citations.
- Produce concise, evidence-grounded claims.
""".strip()


class Synthesizer:
    """Generate grounded claims from collected research evidence."""

    async def synthesize(
        self,
        question: str,
        evidence: list[Evidence],
        conflicts: list[Conflict],
        llm_provider: LLMProvider,
    ) -> SynthesisResult:
        if not question.strip():
            raise ValueError("Research question cannot be empty.")

        if not evidence:
            raise ValueError("Cannot synthesize without evidence.")

        evidence_text = "\n\n".join(
            (
                f"Source ID: {index}\n"
                f"Source title: {item.source.title}\n"
                f"Source URL: {item.source.url}\n"
                f"Claim: {item.claim}\n"
                f"Excerpt: {item.excerpt}"
            )
            for index, item in enumerate(evidence, start=1)
        )

        conflicts_text = "\n\n".join(
            (
                f"Conflict {index}:\n"
                f"Claim A: {conflict.claim_a}\n"
                f"Claim B: {conflict.claim_b}\n"
                f"Possible explanation: {conflict.possible_explanation}\n"
                f"Confidence: {conflict.confidence}"
            )
            for index, conflict in enumerate(conflicts, start=1)
        )

        messages = [
            {
                "role": "system",
                "content": SYNTHESIZER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    f"Research question:\n{question.strip()}\n\n"
                    f"Evidence:\n{evidence_text}\n\n"
                    f"Conflicts:\n{conflicts_text or 'No conflicts identified.'}"
                ),
            },
        ]

        return await llm_provider.generate_structured(
            messages=messages,
            response_model=SynthesisResult,
        )