import pytest

from app.agents.researcher import Researcher
from app.schemas.research import ResearchTask
from app.tools.fake_provider import FakeSearchProvider
from app.tools.web_search import WebSearchTool


@pytest.mark.asyncio
async def test_researcher_executes_search_queries():
    web_search = WebSearchTool(provider=FakeSearchProvider())

    researcher = Researcher(
        tools={
            "web_search": web_search,
        }
    )

    task = ResearchTask(
        question="How does PostgreSQL scale?",
        search_queries=[
            "PostgreSQL horizontal scaling",
            "PostgreSQL sharding",
        ],
        priority=1,
    )

    results = await researcher.execute_task(task)

    assert len(results) == 2
    assert results[0]["success"] is True
    assert results[1]["success"] is True

@pytest.mark.asyncio
async def test_researcher_respects_max_tool_calls():
    web_search = WebSearchTool(provider=FakeSearchProvider())

    researcher = Researcher(
        tools={"web_search": web_search},
        max_concurrent_queries=3,
        max_tool_calls=2,
    )

    task = ResearchTask(
        question="PostgreSQL research",
        search_queries=[
            "PostgreSQL scaling",
            "PostgreSQL sharding",
            "PostgreSQL replication",
            "PostgreSQL performance",
        ],
        priority=1,
    )

    results = await researcher.execute_task(task)

    assert len(results) == 2
    assert all(result["success"] is True for result in results)

@pytest.mark.asyncio
async def test_researcher_respects_max_research_tasks():
    web_search = WebSearchTool(provider=FakeSearchProvider())

    researcher = Researcher(
        tools={"web_search": web_search},
        max_concurrent_queries=3,
        max_tool_calls=2,
        max_research_tasks=2,
    )

    tasks = [
        ResearchTask(
            question="Task 1",
            search_queries=["query 1"],
            priority=1,
        ),
        ResearchTask(
            question="Task 2",
            search_queries=["query 2"],
            priority=2,
        ),
        ResearchTask(
            question="Task 3",
            search_queries=["query 3"],
            priority=3,
        ),
    ]

    results = await researcher.execute_tasks(tasks)

    assert len(results) == 2
    assert results[0]["question"] == "Task 1"
    assert results[1]["question"] == "Task 2"