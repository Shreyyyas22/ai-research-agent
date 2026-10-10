from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass
from typing import Any

DEFAULT_DATASET_PATH = pathlib.Path(__file__).with_name("dataset.json")


@dataclass(frozen=True)
class EvaluationItem:
    """One curated research question with expected evidence."""

    id: str
    question: str
    category: str
    expected_claims: list[str]
    expected_citation_count: int
    must_contain_keywords: list[str]
    min_evidence: int
    difficulty: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "question": self.question,
            "category": self.category,
            "expected_claims": self.expected_claims,
            "expected_citation_count": self.expected_citation_count,
            "must_contain_keywords": self.must_contain_keywords,
            "min_evidence": self.min_evidence,
            "difficulty": self.difficulty,
        }


def load_dataset(path: str | pathlib.Path | None = None) -> list[EvaluationItem]:
    """Load curated dataset; validates required fields and reuses existing schemas."""
    p = pathlib.Path(path) if path is not None else DEFAULT_DATASET_PATH
    raw = json.loads(p.read_text())
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"Dataset at {p} must be a non-empty list")
    items: list[EvaluationItem] = []
    seen: set[str] = set()
    for idx, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"Entry {idx} must be an object")
        for field in ("id", "question", "expected_claims", "expected_citation_count"):
            if field not in entry:
                raise ValueError(f"Entry {idx} missing required field: {field}")
        eid = str(entry["id"]).strip()
        if not eid:
            raise ValueError(f"Entry {idx} has empty id")
        if eid in seen:
            raise ValueError(f"Duplicate id: {eid}")
        seen.add(eid)
        q = str(entry["question"]).strip()
        if not q:
            raise ValueError(f"Entry {eid} has empty question")
        # flexible defaults keep dataset tolerant
        item = EvaluationItem(
            id=eid,
            question=q,
            category=str(entry.get("category", "general")),
            expected_claims=[str(c) for c in entry.get("expected_claims", [])],
            expected_citation_count=int(entry.get("expected_citation_count", 1)),
            must_contain_keywords=[str(k) for k in entry.get("must_contain_keywords", [])],
            min_evidence=int(entry.get("min_evidence", 1)),
            difficulty=str(entry.get("difficulty", "medium")),
        )
        if item.expected_citation_count < 0:
            raise ValueError(f"Entry {eid} has negative expected_citation_count")
        if item.min_evidence < 0:
            raise ValueError(f"Entry {eid} has negative min_evidence")
        items.append(item)
    return items
