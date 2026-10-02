from app.schemas.research import Source
from app.services.research_service import (
    deduplicate_sources,
    normalize_url,
)
from app.services.research_service import ResearchService


def test_normalize_url_removes_tracking_parameters():
    url = (
        "https://Example.com/article/"
        "?utm_source=google&utm_campaign=test"
    )

    assert normalize_url(url) == "https://example.com/article"


def test_normalize_url_removes_fragment():
    url = "https://example.com/article#section-2"

    assert normalize_url(url) == "https://example.com/article"


def test_normalize_url_preserves_meaningful_query_parameters():
    url = (
        "https://example.com/search"
        "?q=postgresql&utm_source=google"
    )

    assert normalize_url(url) == (
        "https://example.com/search?q=postgresql"
    )

def test_deduplicate_sources_removes_duplicate_urls():
    sources = [
        Source(
            title="PostgreSQL Article",
            url="https://example.com/postgres",
        ),
        Source(
            title="PostgreSQL Article Duplicate",
            url="https://example.com/postgres/",
        ),
    ]

    result = deduplicate_sources(sources)

    assert len(result) == 1
    assert result[0].url == "https://example.com/postgres"


def test_deduplicate_sources_keeps_distinct_pages():
    sources = [
        Source(
            title="PostgreSQL",
            url="https://example.com/postgres",
        ),
        Source(
            title="MongoDB",
            url="https://example.com/mongodb",
        ),
    ]

    result = deduplicate_sources(sources)

    assert len(result) == 2

def test_collect_sources_deduplicates_search_results():
    search_results = [
        {
            "success": True,
            "results": [
                {
                    "title": "PostgreSQL Article",
                    "url": "https://example.com/postgres",
                    "snippet": "PostgreSQL information",
                },
                {
                    "title": "PostgreSQL Duplicate",
                    "url": "https://example.com/postgres/?utm_source=google",
                    "snippet": "Duplicate result",
                },
                {
                    "title": "MongoDB Article",
                    "url": "https://example.com/mongodb",
                    "snippet": "MongoDB information",
                },
            ],
        }
    ]

    service = ResearchService()

    sources = service.collect_sources(search_results)

    assert len(sources) == 2

    assert sources[0].url == "https://example.com/postgres"
    assert sources[1].url == "https://example.com/mongodb"


def test_collect_sources_ignores_failed_searches():
    search_results = [
        {
            "success": False,
            "results": [],
            "error": "Search failed",
        }
    ]

    service = ResearchService()

    sources = service.collect_sources(search_results)

    assert sources == []


def test_collect_sources_ignores_invalid_results():
    search_results = [
        {
            "success": True,
            "results": [
                {
                    "title": "",
                    "url": "",
                    "snippet": "Invalid result",
                },
                {
                    "title": "Valid Article",
                    "url": "https://example.com/article",
                    "snippet": "Valid result",
                },
            ],
        }
    ]

    service = ResearchService()

    sources = service.collect_sources(search_results)

    assert len(sources) == 1
    assert sources[0].title == "Valid Article"