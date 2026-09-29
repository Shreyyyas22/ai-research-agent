from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.state import ResearchState


def analyze_query(state: ResearchState) -> dict[str, Any]:
    print("[analyze_query] → validating question")
    return {
        "question": state["question"],
    }


def create_research_plan(state: ResearchState) -> dict[str, Any]:
    print("[create_research_plan] → initializing research plan")
    return {
        "plan": None,
        "research_tasks": [],
    }


def execute_tasks(state: ResearchState) -> dict[str, Any]:
    print("[execute_tasks] → initializing task results")
    return {
        "sources": [],
    }


def collect_evidence(state: ResearchState) -> dict[str, Any]:
    print("[collect_evidence] → initializing evidence")
    return {
        "evidence": [],
    }


def evaluate_sources(state: ResearchState) -> dict[str, Any]:
    print("[evaluate_sources] → marking research as sufficient")
    return {
        "research_sufficient": True,
    }


def synthesize_findings(state: ResearchState) -> dict[str, Any]:
    print("[synthesize_findings] → initializing findings")
    return {
        "findings": [],
    }


def generate_citations(state: ResearchState) -> dict[str, Any]:
    print("[generate_citations] → initializing citations")
    return {
        "citations": [],
    }


def evaluate_report(state: ResearchState) -> dict[str, Any]:
    print("[evaluate_report] → initializing report evaluation")
    return {
        "report": None,
    }


def finalize_report(state: ResearchState) -> dict[str, Any]:
    print("[finalize_report] → finalizing report")
    return state


def build_research_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("analyze_query", analyze_query)
    graph.add_node("create_research_plan", create_research_plan)
    graph.add_node("execute_tasks", execute_tasks)
    graph.add_node("collect_evidence", collect_evidence)
    graph.add_node("evaluate_sources", evaluate_sources)
    graph.add_node("synthesize_findings", synthesize_findings)
    graph.add_node("generate_citations", generate_citations)
    graph.add_node("evaluate_report", evaluate_report)
    graph.add_node("finalize_report", finalize_report)

    graph.add_edge(START, "analyze_query")
    graph.add_edge("analyze_query", "create_research_plan")
    graph.add_edge("create_research_plan", "execute_tasks")
    graph.add_edge("execute_tasks", "collect_evidence")
    graph.add_edge("collect_evidence", "evaluate_sources")
    graph.add_edge("evaluate_sources", "synthesize_findings")
    graph.add_edge("synthesize_findings", "generate_citations")
    graph.add_edge("generate_citations", "evaluate_report")
    graph.add_edge("evaluate_report", "finalize_report")
    graph.add_edge("finalize_report", END)

    return graph.compile()