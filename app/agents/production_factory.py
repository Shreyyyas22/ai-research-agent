from __future__ import annotations

import os

from app.agents.evaluator import ReportEvaluator
from app.agents.graph import build_research_graph
from app.agents.planner import ResearchPlanner
from app.agents.researcher import Researcher
from app.agents.synthesizer import Synthesizer
from app.db.redis import RedisJobStore
from app.llm.groq import GroqProvider
from app.services.citation_service import CitationService
from app.services.progress_publisher import ResearchProgressPublisher
from app.services.report_service import ReportService
from app.services.research_service import ResearchService
from app.services.source_evaluation_service import SourceEvaluationService
from app.tools.tavily_provider import TavilySearchProvider
from app.tools.web_fetch import WebFetchTool
from app.tools.web_search import WebSearchTool


def build_production_research_graph(
    research_id: str,
    job_store: RedisJobStore,
):
    """Build the production graph after validating required credentials."""
    llm_provider_name = os.getenv("LLM_PROVIDER", "groq").lower()
    if llm_provider_name == "gemini":
        required_keys = ("GEMINI_API_KEY", "TAVILY_API_KEY")
        provider_label = "Gemini"
    else:
        required_keys = ("GROQ_API_KEY", "TAVILY_API_KEY")
        provider_label = "Groq"
        llm_provider_name = "groq"

    missing = [name for name in required_keys if not os.getenv(name)]
    if missing:
        raise ValueError(
            f"Missing required research credentials for {provider_label}: " + ", ".join(missing)
        )

    if llm_provider_name == "gemini":
        from app.llm.gemini import GeminiProvider

        llm_provider = GeminiProvider()
    else:
        llm_provider = GroqProvider()
    search_provider = TavilySearchProvider()

    researcher = Researcher(
        tools={"web_search": WebSearchTool(search_provider)}
    )

    return build_research_graph(
        researcher=researcher,
        research_service=ResearchService(),
        planner=ResearchPlanner(llm_provider=llm_provider),
        evaluation_service=SourceEvaluationService(),
        llm_provider=llm_provider,
        synthesizer=Synthesizer(),
        citation_service=CitationService(),
        report_service=ReportService(),
        report_evaluator=ReportEvaluator(),
        progress_callback=ResearchProgressPublisher(research_id, job_store),
        web_fetch_tool=WebFetchTool(),
    )
