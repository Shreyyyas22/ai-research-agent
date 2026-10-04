from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    question: str
    plan: Any
    research_tasks: list[Any]
    sources: list[Any]
    evidence: list[Any]
    conflicts: list[Any]
    findings: Any
    citations: list[Any]
    report: Any
    research_sufficient: bool
    report_evaluation: Any
    evaluation_iteration: int