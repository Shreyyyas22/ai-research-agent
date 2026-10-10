import json
import pathlib

import pytest

from app.eval.dataset import EvaluationItem, load_dataset


def test_load_default_dataset_has_10_items():
    items = load_dataset()
    assert len(items) == 10
    ids = [i.id for i in items]
    assert len(set(ids)) == 10
    # ensure categories cover the four pillars
    cats = {i.category for i in items}
    assert "citation_grounding" in cats
    assert "vector_db" in cats


def test_dataset_items_have_required_fields():
    for item in load_dataset():
        assert item.question.strip()
        assert isinstance(item.expected_claims, list)
        assert item.expected_citation_count >= 0
        assert item.min_evidence >= 0
        assert item.difficulty in {"easy", "medium", "hard"}


def test_load_dataset_rejects_duplicate_ids(tmp_path):
    bad = [
        {"id": "dup", "question": "q1", "expected_claims": [], "expected_citation_count": 1},
        {"id": "dup", "question": "q2", "expected_claims": [], "expected_citation_count": 1},
    ]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="Duplicate id"):
        load_dataset(p)


def test_load_dataset_rejects_missing_field(tmp_path):
    bad = [{"id": "x", "question": "q"}]  # missing expected_claims / citation_count
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="missing required"):
        load_dataset(p)


def test_load_dataset_accepts_flexible_defaults(tmp_path):
    minimal = [{"id": "min-1", "question": "What is X?", "expected_claims": [], "expected_citation_count": 0}]
    p = tmp_path / "min.json"
    p.write_text(json.dumps(minimal))
    items = load_dataset(p)
    assert items[0].category == "general"
    assert items[0].must_contain_keywords == []
