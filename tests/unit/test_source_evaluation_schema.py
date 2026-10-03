import pytest
from pydantic import ValidationError

from app.schemas.research import (
    Conflict,
    EvidenceSufficiency,
    SourceEvaluation,
)


def test_conflict_accepts_valid_data():
    conflict = Conflict(
        claim_a="PostgreSQL performs better for workload A.",
        claim_b="MongoDB performs better for workload A.",
        possible_explanation="The benchmarks used different workloads.",
        confidence="medium",
    )

    assert conflict.claim_a.startswith("PostgreSQL")
    assert conflict.claim_b.startswith("MongoDB")
    assert conflict.confidence == "medium"


def test_evidence_sufficiency_accepts_valid_data():
    result = EvidenceSufficiency(
        sufficient=False,
        reasoning="The evidence does not cover database scalability.",
        missing_information=[
            "Scalability benchmarks",
            "Production workload characteristics",
        ],
    )

    assert result.sufficient is False
    assert len(result.missing_information) == 2


def test_evidence_sufficiency_defaults_to_no_missing_information():
    result = EvidenceSufficiency(
        sufficient=True,
        reasoning="The evidence directly answers the question.",
    )

    assert result.missing_information == []


def test_source_evaluation_accepts_sufficiency_and_conflicts():
    result = SourceEvaluation(
        sufficiency={
            "sufficient": True,
            "reasoning": "The evidence covers the main question.",
            "missing_information": [],
        },
        conflicts=[
            {
                "claim_a": "Source A says X.",
                "claim_b": "Source B says Y.",
                "possible_explanation": "Different experimental conditions.",
                "confidence": "medium",
            }
        ],
    )

    assert result.sufficiency.sufficient is True
    assert len(result.conflicts) == 1


def test_source_evaluation_rejects_extra_fields():
    with pytest.raises(ValidationError):
        SourceEvaluation(
            sufficiency={
                "sufficient": True,
                "reasoning": "Enough evidence.",
            },
            conflicts=[],
            unexpected_field="should fail",
        )


def test_conflict_rejects_extra_fields():
    with pytest.raises(ValidationError):
        Conflict(
            claim_a="Claim A",
            claim_b="Claim B",
            possible_explanation="Different context.",
            confidence="medium",
            unexpected_field="should fail",
        )