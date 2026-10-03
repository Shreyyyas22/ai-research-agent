from app.schemas.research import SynthesizedClaim, SynthesisResult
from app.services.citation_service import (
    CitationService,
    CitationValidationError,
)


def test_invalid_citation_id_is_detected():
    synthesis = SynthesisResult(
        claims=[
            SynthesizedClaim(
                claim="PostgreSQL supports JSONB.",
                citation_ids=[99],
            )
        ]
    )

    service = CitationService()

    try:
        service.validate(
            synthesis=synthesis,
            valid_source_ids={1, 2},
        )
    except CitationValidationError:
        return

    raise AssertionError(
        "Citation validator failed to detect invalid citation ID 99."
    )