from abc import ABC, abstractmethod
from typing import Any


class Reranker(ABC):
    """Interface for second-stage retrieval reranking."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Rerank retrieval candidates for the given query."""
        raise NotImplementedError


class PassthroughReranker(Reranker):
    """Baseline reranker that preserves the existing ranking."""

    def rerank(
        self,
        query: str,
        results: list[dict[str, Any]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        return results[:top_k]