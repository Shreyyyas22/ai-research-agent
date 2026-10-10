import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.state import ResearchState
from app.agents.planner import ResearchPlanner
from app.services.report_service import ReportService
from app.agents.researcher import Researcher
from app.services.research_service import ResearchService
from app.tools.web_fetch import WebFetchTool
from app.agents.instrumented_graph import InstrumentedResearchGraph
from app.observability.logging import observe_node


async def _emit_progress(
    progress_callback: Any,
    progress: str,
) -> None:
    """
    Emit a progress message if a callback was provided.

    Supports both synchronous and asynchronous callbacks.
    """

    if progress_callback is None:
        return

    result = progress_callback(progress)

    if hasattr(result, "__await__"):
        await result


async def analyze_query(
    state: ResearchState,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print("[analyze_query] → validating question")

    await _emit_progress(
        progress_callback,
        "analyzing_query",
    )

    return {
        "question": state["question"],
    }


async def create_research_plan(
    state: ResearchState,
    planner: ResearchPlanner,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[create_research_plan] "
        "→ creating research plan"
    )

    await _emit_progress(
        progress_callback,
        "planning",
    )

    plan = await planner.create_plan(
        state["question"],
    )

    return {
        "plan": plan,
        "research_tasks": plan.tasks,
    }



async def execute_tasks(
    state: ResearchState,
    researcher: Researcher,
    research_service: ResearchService,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print("[execute_tasks] → executing research tasks")

    await _emit_progress(progress_callback, "researching")

    tasks = state.get("research_tasks", [])

    if not tasks:
        return {
            "task_results": [],
            "sources": state.get("sources", []),
        }

    # Execute the planned tasks using the registered search tool.
    task_results = await researcher.execute_tasks(tasks)

    # Flatten search responses from all research tasks.
    search_results = [
        search_result
        for task_result in task_results
        for search_result in task_result.get("results", [])
    ]

    # Convert search responses into deduplicated Source objects.
    discovered_sources = research_service.collect_sources(
        search_results
    )

    # Preserve existing sources and avoid duplicate URLs.
    sources = research_service.collect_sources(
        [
            {
                "success": True,
                "results": [
                    {
                        "title": source.title,
                        "url": source.url,
                        "snippet": "",
                    }
                    for source in [
                        *state.get("sources", []),
                        *discovered_sources,
                    ]
                ],
            }
        ]
    )

    print(
        f"[execute_tasks] → collected {len(sources)} unique sources"
    )

    return {
        "task_results": task_results,
        "sources": sources,
    }



async def collect_evidence(
    state: ResearchState,
    web_fetch_tool: WebFetchTool,
    research_service: ResearchService,
    llm_provider: Any,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[collect_evidence] "
        "→ fetching sources and extracting evidence"
    )

    await _emit_progress(
        progress_callback,
        "collecting_evidence",
    )

    evidence = list(state.get("evidence", []))
    extracted_source_urls = {
        item.source.url
        for item in evidence
    }

    # Limit to first 5 new sources to stay within free-tier TPM and keep smoke test fast
    for source in list(state.get("sources", []))[:5]:
        if source.url in extracted_source_urls:
            continue

        fetched = await web_fetch_tool.execute(
            {"url": source.url}
        )

        if not fetched.get("success"):
            print(
                "[collect_evidence] "
                f"→ unable to fetch {source.url}: "
                f"{fetched.get('error', 'unknown error')}"
            )
            continue

        content = fetched.get("content", "")

        if not isinstance(content, str) or not content.strip():
            continue

        extracted = await research_service.extract_evidence(
            source=source,
            content=content,
            llm_provider=llm_provider,
        )
        evidence.extend(extracted)

    print(
        f"[collect_evidence] → collected {len(evidence)} evidence items"
    )

    return {"evidence": evidence}


async def evaluate_sources(
    state: ResearchState,
    evaluation_service: Any,
    llm_provider: Any,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[evaluate_sources] "
        "→ evaluating evidence"
    )

    await _emit_progress(
        progress_callback,
        "evaluating_evidence",
    )

    evaluation = await evaluation_service.evaluate(
        question=state["question"],
        evidence=state.get(
            "evidence",
            [],
        ),
        llm_provider=llm_provider,
    )

    return {
        "research_sufficient": (
            evaluation.sufficiency.sufficient
        ),
        "conflicts": evaluation.conflicts,
    }


async def synthesize_findings(
    state: ResearchState,
    synthesizer: Any,
    citation_service: Any,
    llm_provider: Any,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[synthesize_findings] "
        "→ synthesizing findings"
    )

    await _emit_progress(
        progress_callback,
        "synthesizing",
    )

    synthesis = await synthesizer.synthesize(
        question=state["question"],
        evidence=state.get(
            "evidence",
            [],
        ),
        conflicts=state.get(
            "conflicts",
            [],
        ),
        llm_provider=llm_provider,
    )

    valid_source_ids = set(
        range(
            1,
            len(
                state.get(
                    "evidence",
                    [],
                )
            )
            + 1,
        )
    )

    validated_synthesis = citation_service.validate(
        synthesis=synthesis,
        valid_source_ids=valid_source_ids,
    )

    return {
        "findings": validated_synthesis,
    }


async def generate_citations(
    state: ResearchState,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[generate_citations] "
        "→ collecting validated citation IDs"
    )

    await _emit_progress(
        progress_callback,
        "generating_citations",
    )

    synthesis = state["findings"]

    citation_ids = sorted(
        {
            citation_id
            for claim in synthesis.claims
            for citation_id in claim.citation_ids
        }
    )

    return {
        "citations": citation_ids,
    }


async def build_report(
    state: ResearchState,
    report_service: ReportService,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[build_report] "
        "→ building structured research report"
    )

    await _emit_progress(
        progress_callback,
        "building_report",
    )

    synthesis = state["findings"]

    report = report_service.build_report(
        question=state["question"],
        synthesis=synthesis,
        evidence=state.get(
            "evidence",
            [],
        ),
        sources=state.get(
            "sources",
            [],
        ),
        conflicts=state.get(
            "conflicts",
            [],
        ),
    )

    return {
        "report": report,
    }


async def evaluate_report(
    state: ResearchState,
    evaluator: Any,
    llm_provider: Any,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[evaluate_report] "
        "→ evaluating generated report"
    )

    await _emit_progress(
        progress_callback,
        "evaluating_report",
    )

    report = state.get("report")

    if report is None:
        raise ValueError(
            "Cannot evaluate a missing report."
        )

    evaluation = await evaluator.evaluate(
        question=state["question"],
        report=report,
        evidence=state.get(
            "evidence",
            [],
        ),
        llm_provider=llm_provider,
    )

    current_iteration = state.get(
        "evaluation_iteration",
        0,
    )

    return {
        "report_evaluation": evaluation,
        "evaluation_iteration": (
            current_iteration + 1
        ),
    }


def route_after_report_evaluation(
    state: ResearchState,
    max_evaluation_iterations: int,
) -> str:
    """Route based on report quality with a bounded retry loop."""

    evaluation = state.get(
        "report_evaluation"
    )

    if evaluation is None:
        raise ValueError(
            "Report evaluation is missing."
        )

    current_iteration = state.get(
        "evaluation_iteration",
        0,
    )

    if evaluation.score >= 4:
        return "finalize_report"

    if (
        current_iteration
        >= max_evaluation_iterations
    ):
        return "finalize_report"

    return "execute_tasks"


async def finalize_report(
    state: ResearchState,
    progress_callback: Any = None,
) -> dict[str, Any]:
    print(
        "[finalize_report] "
        "→ finalizing report"
    )

    await _emit_progress(
        progress_callback,
        "completed",
    )

    return state


def route_after_evaluation(
    state: ResearchState,
) -> str:
    """Route research based on evidence sufficiency."""

    if state.get(
        "research_sufficient",
        False,
    ):
        return "synthesize_findings"

    return "execute_tasks"


def build_research_graph(
    researcher: Researcher,
    research_service: ResearchService,
    planner: ResearchPlanner,
    evaluation_service: Any,
    llm_provider: Any,
    synthesizer: Any,
    citation_service: Any,
    report_service: ReportService,
    report_evaluator: Any,
    max_evaluation_iterations: int = 2,
    max_agent_iterations: int | None = None,
    max_llm_calls: int | None = None,
    max_tool_calls: int | None = None,
    max_research_time: float | None = None,
    progress_callback: Any = None,
    web_fetch_tool: WebFetchTool | None = None,
):
    effective_max_iterations = (
        max_agent_iterations
        if max_agent_iterations is not None
        else (
            int(os.getenv("MAX_AGENT_ITERATIONS"))
            if os.getenv("MAX_AGENT_ITERATIONS")
            else max_evaluation_iterations
        )
    )
    if effective_max_iterations < 1:
        raise ValueError("MAX_AGENT_ITERATIONS must be at least 1.")

    graph = StateGraph(
        ResearchState
    )

    web_fetch_tool = web_fetch_tool or WebFetchTool()

    async def analyze_query_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await analyze_query(
            state,
            progress_callback,
        )

    async def create_research_plan_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await create_research_plan(
            state,
            planner,
            progress_callback,
        )

    async def execute_tasks_node(state: ResearchState):
        return await execute_tasks(
            state=state,
            researcher=researcher,
            research_service=research_service,
            progress_callback=progress_callback,
        )

    async def collect_evidence_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await collect_evidence(
            state=state,
            web_fetch_tool=web_fetch_tool,
            research_service=research_service,
            llm_provider=llm_provider,
            progress_callback=progress_callback,
        )

    graph.add_node(
        "analyze_query",
        observe_node("analyze_query", analyze_query_node),
    )

    graph.add_node(
        "create_research_plan",
        observe_node("create_research_plan", create_research_plan_node),
    )

    graph.add_node(
        "execute_tasks",
        observe_node("execute_tasks", execute_tasks_node),
    )

    graph.add_node(
        "collect_evidence",
        observe_node("collect_evidence", collect_evidence_node),
    )

    async def evaluate_sources_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await evaluate_sources(
            state,
            evaluation_service,
            llm_provider,
            progress_callback,
        )

    async def synthesize_findings_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await synthesize_findings(
            state,
            synthesizer,
            citation_service,
            llm_provider,
            progress_callback,
        )

    async def evaluate_report_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await evaluate_report(
            state,
            report_evaluator,
            llm_provider,
            progress_callback,
        )

    graph.add_node(
        "evaluate_sources",
        observe_node("evaluate_sources", evaluate_sources_node),
    )

    graph.add_node(
        "synthesize_findings",
        observe_node("synthesize_findings", synthesize_findings_node),
    )

    async def generate_citations_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await generate_citations(
            state,
            progress_callback,
        )

    graph.add_node(
        "generate_citations",
        observe_node("generate_citations", generate_citations_node),
    )

    async def build_report_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await build_report(
            state,
            report_service,
            progress_callback,
        )

    graph.add_node(
        "build_report",
        observe_node("build_report", build_report_node),
    )

    graph.add_node(
        "evaluate_report",
        observe_node("evaluate_report", evaluate_report_node),
    )

    async def finalize_report_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await finalize_report(
            state,
            progress_callback,
        )


    graph.add_node(
        "finalize_report",
        observe_node("finalize_report", finalize_report_node),
    )

    # ---------------------------------------------------------------
    # Main flow
    # ---------------------------------------------------------------

    graph.add_edge(
        START,
        "analyze_query",
    )

    graph.add_edge(
        "analyze_query",
        "create_research_plan",
    )

    graph.add_edge(
        "create_research_plan",
        "execute_tasks",
    )

    graph.add_edge(
        "execute_tasks",
        "collect_evidence",
    )

    graph.add_edge(
        "collect_evidence",
        "evaluate_sources",
    )

    # ---------------------------------------------------------------
    # Evidence sufficiency routing
    # ---------------------------------------------------------------

    graph.add_conditional_edges(
        "evaluate_sources",
        route_after_evaluation,
        {
            "synthesize_findings": (
                "synthesize_findings"
            ),
            "execute_tasks": "execute_tasks",
        },
    )

    # ---------------------------------------------------------------
    # Synthesis → Citations → Report → Evaluation
    # ---------------------------------------------------------------

    graph.add_edge(
        "synthesize_findings",
        "generate_citations",
    )

    graph.add_edge(
        "generate_citations",
        "build_report",
    )

    graph.add_edge(
        "build_report",
        "evaluate_report",
    )

    def route_report_evaluation(
        state: ResearchState,
    ) -> str:
        return route_after_report_evaluation(
            state,
            effective_max_iterations,
        )

    graph.add_conditional_edges(
        "evaluate_report",
        route_report_evaluation,
        {
            "finalize_report": (
                "finalize_report"
            ),
            "execute_tasks": "execute_tasks",
        },
    )

    graph.add_edge(
        "finalize_report",
        END,
    )

    return InstrumentedResearchGraph(
        graph.compile(),
        max_llm_calls=max_llm_calls,
        max_tool_calls=max_tool_calls,
        max_research_time=max_research_time,
        max_agent_iterations=effective_max_iterations,
    )

