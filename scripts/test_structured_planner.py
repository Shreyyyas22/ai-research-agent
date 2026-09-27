import asyncio
from email import message

from app.llm.groq import GroqProvider
from app.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.schemas.research import ResearchPlan

async def main() -> None:
    provider = GroqProvider()

    question = (
        "Should an e-commerce company use PostgreSQL or MongoDB?"
    )

    messages = [
        {
            "role": "system",
            "content": PLANNER_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": question,
        },
    ]

    plan = await provider.generate_structured(
        messages=messages,
        response_model=ResearchPlan,
    )

    print("\nRESEARCH PLAN\n")

    for index, task in enumerate(plan.tasks, start=1):
        print(f"Task {index}")
        print(f"Question: {task.question}")
        print(f"Search queries: {task.search_queries}")
        print(f"Priority: {task.priority}")
        print()


if __name__ == "__main__":
    asyncio.run(main())