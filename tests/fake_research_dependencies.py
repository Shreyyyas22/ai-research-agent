
from app.agents.researcher import Researcher
from app.services.research_service import ResearchService
from app.tools.fake_provider import FakeSearchProvider
from app.tools.web_search import WebSearchTool


def build_fake_research_dependencies():
    researcher = Researcher(
        tools={
            "web_search": WebSearchTool(
                FakeSearchProvider()
            )
        }
    )

    return {
        "researcher": researcher,
        "research_service": ResearchService(),
    }
