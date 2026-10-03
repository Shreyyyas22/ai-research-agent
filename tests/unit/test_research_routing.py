from app.agents.graph import route_after_evaluation


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