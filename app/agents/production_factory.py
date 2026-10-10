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
    """Build the production graph with Groq→Gemini fallback on daily quota."""
    llm_provider_name = os.getenv("LLM_PROVIDER", "groq").lower()

    has_groq = bool(os.getenv("GROQ_API_KEY"))
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_tavily = bool(os.getenv("TAVILY_API_KEY"))

    if llm_provider_name == "gemini":
        missing = []
        if not has_gemini:
            missing.append("GEMINI_API_KEY")
        if not has_tavily:
            missing.append("TAVILY_API_KEY")
        if missing:
            raise ValueError("Missing required research credentials: " + ", ".join(missing))
        from app.llm.gemini import GeminiProvider

        llm_provider = GeminiProvider()
    elif llm_provider_name == "auto":
        # Auto: prefer Groq, fallback to Gemini on daily quota if both keys present
        if not has_groq and not has_gemini:
            missing = []
            if not has_groq:
                missing.append("GROQ_API_KEY")
            if not has_gemini:
                missing.append("GEMINI_API_KEY")
            if not has_tavily:
                missing.append("TAVILY_API_KEY")
            raise ValueError("Missing required research credentials: " + ", ".join(missing))
        if not has_tavily:
            raise ValueError("Missing required research credentials: TAVILY_API_KEY")
        if has_groq and has_gemini:
            from app.llm.fallback import FallbackProvider
            from app.llm.gemini import GeminiProvider

            llm_provider = FallbackProvider(GroqProvider(), GeminiProvider())
        elif has_groq:
            llm_provider = GroqProvider()
        else:
            from app.llm.gemini import GeminiProvider

            llm_provider = GeminiProvider()
    else:
        # groq (default) with optional fallback to gemini
        missing = []
        if not has_tavily:
            missing.append("TAVILY_API_KEY")
        # For default groq, require GROQ unless GEMINI fallback is explicitly intended
        # But to keep backward compat with existing test, require GROQ
        if not has_groq:
            missing.append("GROQ_API_KEY")
        if missing:
            raise ValueError("Missing required research credentials: " + ", ".join(missing))
        if has_groq and has_gemini:
            from app.llm.fallback import FallbackProvider
            from app.llm.gemini import GeminiProvider

            llm_provider = FallbackProvider(GroqProvider(), GeminiProvider())
        elif has_groq:
            llm_provider = GroqProvider()
        elif has_gemini:
            from app.llm.gemini import GeminiProvider

            llm_provider = GeminiProvider()
        else:
            raise ValueError("Missing required research credentials for Groq: GROQ_API_KEY")
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
