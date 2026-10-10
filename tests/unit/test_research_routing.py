from app.agents.graph import (
    route_after_evaluation,
    route_after_report_evaluation,
)
from app.schemas.research import ReportEvaluation


def test_route_to_synthesis_when_research_is_sufficient():
    state = {
        "research_sufficient": True,
    }

    assert route_after_evaluation(state) == "synthesize_findings"


def test_route_to_research_when_evidence_is_insufficient():
    state = {
        "research_sufficient": False,
    }

    assert route_after_evaluation(state) == "execute_tasks"


def test_route_to_research_when_sufficiency_is_missing():
    state = {}

    assert route_after_evaluation(state) == "execute_tasks"


def test_route_after_report_evaluation_stops_at_max_agent_iterations():
    low_evaluation = ReportEvaluation(
        grounded=False,
        citation_correct=False,
        hallucination_detected=True,
        score=2,
        reasoning="Low quality report",
        unsupported_claims=["Claim 1"],
    )

    state = {
        "report_evaluation": low_evaluation,
        "evaluation_iteration": 3,
    }

    # Stopping when iteration count reaches max_agent_iterations (3)
    assert route_after_report_evaluation(state, max_evaluation_iterations=3) == "finalize_report"

    # Continuing when iteration count is under max_agent_iterations (3)
    state["evaluation_iteration"] = 2
    assert route_after_report_evaluation(state, max_evaluation_iterations=3) == "execute_tasks"