import pytest
from pydantic import ValidationError

from app.schemas.research import ReportEvaluation


def test_valid_report_evaluation():
    evaluation = ReportEvaluation(
        grounded=True,
        citation_correct=True,
        hallucination_detected=False,
        score=5,
        reasoning="All claims are supported by the supplied evidence.",
        unsupported_claims=[],
    )

    assert evaluation.grounded is True
    assert evaluation.citation_correct is True
    assert evaluation.hallucination_detected is False
    assert evaluation.score == 5
    assert evaluation.unsupported_claims == []


def test_report_evaluation_with_unsupported_claims():
    evaluation = ReportEvaluation(
        grounded=False,
        citation_correct=False,
        hallucination_detected=True,
        score=2,
        reasoning="The report contains an unsupported claim.",
        unsupported_claims=[
            "PostgreSQL is 50% faster than MongoDB."
        ],
    )

    assert evaluation.grounded is False
    assert evaluation.citation_correct is False
    assert evaluation.hallucination_detected is True
    assert evaluation.score == 2
    assert len(evaluation.unsupported_claims) == 1


def test_score_cannot_be_below_one():
    with pytest.raises(ValidationError):
        ReportEvaluation(
            grounded=False,
            citation_correct=False,
            hallucination_detected=True,
            score=0,
            reasoning="Invalid score.",
        )


def test_score_cannot_be_above_five():
    with pytest.raises(ValidationError):
        ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=6,
            reasoning="Invalid score.",
        )


def test_report_evaluation_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ReportEvaluation(
            grounded=True,
            citation_correct=True,
            hallucination_detected=False,
            score=5,
            reasoning="Valid evaluation.",
            unexpected_field="not allowed",
        )