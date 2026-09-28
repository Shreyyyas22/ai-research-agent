import pytest

from app.agents.planner import ResearchPlanner
from app.schemas.research import ResearchPlan, ResearchTask


class FakeLLMProvider:
    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type,
        **kwargs,
    ):
        return ResearchPlan(
            tasks=[
                ResearchTask(
                    question="How does PostgreSQL perform under high load?",
                    search_queries=[
                        "PostgreSQL high traffic performance",
                        "PostgreSQL scalability benchmarks",
                    ],
                    priority=5,
                ),
                ResearchTask(
                    question="How does MongoDB scale under high traffic?",
                    search_queries=[
                        "MongoDB high traffic scalability",
                        "MongoDB performance benchmarks",
                    ],
                    priority=5,
                ),
                ResearchTask(
                    question="How do PostgreSQL and MongoDB differ in transactions?",
                    search_queries=[
                        "PostgreSQL transactions",
                        "MongoDB transactions",
                    ],
                    priority=4,
                ),
            ]
        )


@pytest.mark.asyncio
async def test_planner_creates_research_plan() -> None:
    planner = ResearchPlanner(
        llm_provider=FakeLLMProvider(),
    )

    plan = await planner.create_plan(
        "Should I use PostgreSQL or MongoDB for a high-traffic SaaS application?"
    )

    assert isinstance(plan, ResearchPlan)
    assert len(plan.tasks) == 3
    assert plan.tasks[0].priority == 5
    assert len(plan.tasks[0].search_queries) == 2


@pytest.mark.asyncio
async def test_planner_rejects_empty_question() -> None:
    planner = ResearchPlanner(
        llm_provider=FakeLLMProvider(),
    )

    with pytest.raises(
        ValueError,
        match="Research question cannot be empty",
    ):
        await planner.create_plan("")


@pytest.mark.asyncio
async def test_planner_enforces_max_tasks() -> None:
    planner = ResearchPlanner(
        llm_provider=FakeLLMProvider(),
        max_tasks=2,
    )

    plan = await planner.create_plan(
        "Compare PostgreSQL and MongoDB."
    )

    assert len(plan.tasks) == 2