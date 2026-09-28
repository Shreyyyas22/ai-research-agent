from typing import Any

from app.llm.base import LLMProvider
from app.schemas.research import ResearchPlan


PLANNER_SYSTEM_PROMPT = """
You are a research planning agent.

Your job is to decompose a complex research question
into a small number of focused, independent research tasks.

For each task:
- Define one specific sub-question.
- Provide useful search queries.
- Assign a priority from 1 to 5.
- Avoid overlapping tasks.
- Cover the important dimensions of the original question.

Do not answer the research question yourself.

Return only the requested structured output.
""".strip()


class ResearchPlanner:
    """Create bounded research plans using an LLM provider."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        max_tasks: int = 5,
    ) -> None:
        if max_tasks <= 0:
            raise ValueError("max_tasks must be greater than zero.")

        if max_tasks > 5:
            raise ValueError("max_tasks cannot exceed 5.")

        self.llm_provider = llm_provider
        self.max_tasks = max_tasks

    async def create_plan(
        self,
        question: str,
    ) -> ResearchPlan:
        if not question.strip():
            raise ValueError("Research question cannot be empty.")

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": PLANNER_SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": (
                    "Create a research plan for the following question:\n\n"
                    f"{question.strip()}"
                ),
            },
        ]

        plan = await self.llm_provider.generate_structured(
            messages=messages,
            response_model=ResearchPlan,
        )

        if len(plan.tasks) > self.max_tasks:
            plan.tasks = plan.tasks[: self.max_tasks]

        return plan