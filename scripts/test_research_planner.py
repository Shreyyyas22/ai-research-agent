import asyncio

from app.agents.planner import ResearchPlanner
from app.llm.groq import GroqProvider


QUESTIONS = [
    "Should a high-traffic SaaS application use PostgreSQL or MongoDB?",
    "How can an AI coding assistant retrieve relevant context from a large codebase?",
    "What are the main approaches for deploying a FastAPI application in production?",
]


async def main() -> None:
    llm = GroqProvider()
    planner = ResearchPlanner(llm_provider=llm)

    for number, question in enumerate(QUESTIONS, start=1):
        print("=" * 80)
        print(f"QUESTION {number}")
        print(question)
        print()

        plan = await planner.create_plan(question)

        for index, task in enumerate(plan.tasks, start=1):
            print(f"Task {index}")
            print(f"Question: {task.question}")
            print(f"Priority: {task.priority}")
            print("Search queries:")

            for query in task.search_queries:
                print(f"  - {query}")

            print()


if __name__ == "__main__":
    asyncio.run(main())