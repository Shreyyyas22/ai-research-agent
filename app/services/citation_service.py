from app.schemas.research import SynthesisResult


class CitationValidationError(ValueError):
    """Raised when a synthesis contains invalid citation IDs."""


class CitationService:
    """Validate citation IDs against the retrieved source IDs."""

    def validate(
        self,
        synthesis: SynthesisResult,
        valid_source_ids: set[int],
    ) -> SynthesisResult:
        for synthesized_claim in synthesis.claims:
            invalid_ids = [
                citation_id
                for citation_id in synthesized_claim.citation_ids
                if citation_id not in valid_source_ids
            ]

            if invalid_ids:
                raise CitationValidationError(
                    f"Invalid citation IDs: {invalid_ids}. "
                    f"Valid source IDs are: {sorted(valid_source_ids)}."
                )

        return synthesis