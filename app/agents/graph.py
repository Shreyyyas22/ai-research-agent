from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.state import ResearchState
from app.services.report_service import ReportService


def analyze_query(state: ResearchState) -> dict[str, Any]:
    print("[analyze_query] → validating question")

    return {
        "question": state["question"],
    }


def create_research_plan(state: ResearchState) -> dict[str, Any]:
    print("[create_research_plan] → initializing research plan")

    return {
        "plan": state.get("plan"),
        "research_tasks": state.get("research_tasks", []),
    }


def execute_tasks(state: ResearchState) -> dict[str, Any]:
    print("[execute_tasks] → initializing task results")

    return {
        "sources": state.get("sources", []),
    }


def collect_evidence(state: ResearchState) -> dict[str, Any]:
    print("[collect_evidence] → initializing evidence")

    return {
        "evidence": state.get("evidence", []),
    }


async def evaluate_sources(
    state: ResearchState,
    evaluation_service: Any,
    llm_provider: Any,
) -> dict[str, Any]:
    print("[evaluate_sources] → evaluating evidence")

    evaluation = await evaluation_service.evaluate(
        question=state["question"],
        evidence=state.get("evidence", []),
        llm_provider=llm_provider,
    )

    return {
        "research_sufficient": evaluation.sufficiency.sufficient,
        "conflicts": evaluation.conflicts,
    }


async def synthesize_findings(
    state: ResearchState,
    synthesizer: Any,
    citation_service: Any,
    llm_provider: Any,
) -> dict[str, Any]:
    print("[synthesize_findings] → synthesizing findings")

    synthesis = await synthesizer.synthesize(
        question=state["question"],
        evidence=state.get("evidence", []),
        conflicts=state.get("conflicts", []),
        llm_provider=llm_provider,
    )

    valid_source_ids = set(
        range(
            1,
            len(state.get("evidence", [])) + 1,
        )
    )

    validated_synthesis = citation_service.validate(
        synthesis=synthesis,
        valid_source_ids=valid_source_ids,
    )

    return {
        "findings": validated_synthesis,
    }


def generate_citations(
    state: ResearchState,
) -> dict[str, Any]:
    print("[generate_citations] → collecting validated citation IDs")

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


def build_report(
    state: ResearchState,
    report_service: ReportService,
) -> dict[str, Any]:
    print("[build_report] → building structured research report")

    synthesis = state["findings"]

    report = report_service.build_report(
        question=state["question"],
        synthesis=synthesis,
        evidence=state.get("evidence", []),
        sources=state.get("sources", []),
        conflicts=state.get("conflicts", []),
    )

    return {
        "report": report,
    }


async def evaluate_report(
    state: ResearchState,
    evaluator: Any,
    llm_provider: Any,
) -> dict[str, Any]:
    print("[evaluate_report] → evaluating generated report")

    report = state.get("report")

    if report is None:
        raise ValueError("Cannot evaluate a missing report.")

    evaluation = await evaluator.evaluate(
        question=state["question"],
        report=report,
        evidence=state.get("evidence", []),
        llm_provider=llm_provider,
    )

    current_iteration = state.get(
        "evaluation_iteration",
        0,
    )

    return {
        "report_evaluation": evaluation,
        "evaluation_iteration": current_iteration + 1,
    }
def route_after_report_evaluation(
    state: ResearchState,
    max_evaluation_iterations: int,
) -> str:
    """Route based on report quality with a bounded retry loop."""

    evaluation = state.get("report_evaluation")

    if evaluation is None:
        raise ValueError("Report evaluation is missing.")

    current_iteration = state.get(
        "evaluation_iteration",
        0,
    )

    # Accept a sufficiently grounded report.
    if evaluation.score >= 4:
        return "finalize_report"

    # Stop retrying once the maximum number of evaluations is reached.
    if current_iteration >= max_evaluation_iterations:
        return "finalize_report"

    # Low-quality report → perform another research iteration.
    return "execute_tasks"

def finalize_report(
    state: ResearchState,
) -> dict[str, Any]:
    print("[finalize_report] → finalizing report")

    return state


def route_after_evaluation(
    state: ResearchState,
) -> str:
    """Route research based on evidence sufficiency."""

    if state.get("research_sufficient", False):
        return "synthesize_findings"

    return "execute_tasks"


def build_research_graph(
    evaluation_service: Any,
    llm_provider: Any,
    synthesizer: Any,
    citation_service: Any,
    report_service: ReportService,
    report_evaluator: Any,
    max_evaluation_iterations: int = 2,
):
    graph = StateGraph(ResearchState)

    graph.add_node(
        "analyze_query",
        analyze_query,
    )

    graph.add_node(
        "create_research_plan",
        create_research_plan,
    )

    graph.add_node(
        "execute_tasks",
        execute_tasks,
    )

    graph.add_node(
        "collect_evidence",
        collect_evidence,
    )

    async def evaluate_sources_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await evaluate_sources(
            state,
            evaluation_service,
            llm_provider,
        )

    async def synthesize_findings_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await synthesize_findings(
            state,
            synthesizer,
            citation_service,
            llm_provider,
        )

    async def evaluate_report_node(
        state: ResearchState,
    ) -> dict[str, Any]:
        return await evaluate_report(
            state,
            report_evaluator,
            llm_provider,
        )

    graph.add_node(
        "evaluate_sources",
        evaluate_sources_node,
    )

    graph.add_node(
        "synthesize_findings",
        synthesize_findings_node,
    )

    graph.add_node(
        "generate_citations",
        generate_citations,
    )

    graph.add_node(
        "build_report",
        lambda state: build_report(
            state,
            report_service,
        ),
    )

    graph.add_node(
        "evaluate_report",
        evaluate_report_node,
    )

    graph.add_node(
        "finalize_report",
        finalize_report,
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
            "synthesize_findings": "synthesize_findings",
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
            max_evaluation_iterations,
        )


    graph.add_conditional_edges(
        "evaluate_report",
        route_report_evaluation,
        {
            "finalize_report": "finalize_report",
            "execute_tasks": "execute_tasks",
        },
    )

    graph.add_edge(
        "finalize_report",
        END,
    )

    return graph.compile()