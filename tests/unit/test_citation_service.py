import pytest

from app.schemas.research import SynthesizedClaim, SynthesisResult
from app.services.citation_service import (
    CitationService,
    CitationValidationError,
)


def make_synthesis(citation_ids: list[int]) -> SynthesisResult:
    return SynthesisResult(
        claims=[
            SynthesizedClaim(
                claim="PostgreSQL supports JSONB.",
                citation_ids=citation_ids,
            )
        ]
    )


def test_valid_citations_are_accepted():
    service = CitationService()

    synthesis = make_synthesis([1])

    result = service.validate(
        synthesis=synthesis,
        valid_source_ids={1, 2},
    )

    assert result == synthesis


def test_multiple_valid_citations_are_accepted():
    service = CitationService()

    synthesis = make_synthesis([1, 2])

    result = service.validate(
        synthesis=synthesis,
        valid_source_ids={1, 2, 3},
    )

    assert result == synthesis


def test_invalid_citation_is_rejected():
    service = CitationService()

    synthesis = make_synthesis([99])

    with pytest.raises(CitationValidationError, match="Invalid citation IDs"):
        service.validate(
            synthesis=synthesis,
            valid_source_ids={1, 2},
        )


def test_mixed_valid_and_invalid_citations_are_rejected():
    service = CitationService()

    synthesis = make_synthesis([1, 99])

    with pytest.raises(CitationValidationError, match="99"):
        service.validate(
            synthesis=synthesis,
            valid_source_ids={1, 2},
        )