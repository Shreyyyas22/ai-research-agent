from app.schemas.research import Source
from app.services.research_service import ResearchService


def test_phase_12_checkpoint_deduplicates_near_duplicate_urls():
    service = ResearchService()

    search_results = [
        {
            "success": True,
            "results": [
                {
                    "title": "PostgreSQL Documentation",
                    "url": "https://example.com/postgres?utm_source=google",
                    "snippet": "PostgreSQL documentation",
                },
                {
                    "title": "PostgreSQL Documentation Duplicate",
                    "url": "https://example.com/postgres/",
                    "snippet": "Same PostgreSQL documentation",
                },
            ],
        }
    ]

    sources = service.collect_sources(search_results)

    assert len(sources) == 1
    assert sources[0].url == "https://example.com/postgres"