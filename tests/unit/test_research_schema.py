import pytest
from pydantic import ValidationError

from app.schemas.research import EvidenceExtraction


def test_evidence_extraction_accepts_valid_evidence():
    result = EvidenceExtraction(
        evidence=[
            {
                "claim": "PostgreSQL supports transactions.",
                "excerpt": "PostgreSQL provides full transaction support.",
            }
        ]
    )

    assert len(result.evidence) == 1
    assert result.evidence[0].claim == "PostgreSQL supports transactions."
    assert (
        result.evidence[0].excerpt
        == "PostgreSQL provides full transaction support."
    )


def test_evidence_extraction_allows_empty_evidence():
    result = EvidenceExtraction(evidence=[])

    assert result.evidence == []


def test_evidence_extraction_rejects_extra_fields():
    with pytest.raises(ValidationError):
        EvidenceExtraction(
            evidence=[],
            unexpected_field="should fail",
        )


def test_evidence_extraction_limits_evidence_items():
    evidence = [
        {
            "claim": f"Claim {i}",
            "excerpt": f"Excerpt {i}",
        }
        for i in range(11)
    ]

    with pytest.raises(ValidationError):
        EvidenceExtraction(evidence=evidence)