import math
import re
from collections import Counter
from typing import Any


class BM25:
    """Simple BM25 lexical retrieval over an in-memory document collection."""

    def __init__(
        self,
        documents: list[dict[str, Any]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        if k1 < 0:
            raise ValueError("k1 must be non-negative.")

        if not 0 <= b <= 1:
            raise ValueError("b must be between 0 and 1.")

        self.documents = documents
        self.k1 = k1
        self.b = b

        self.tokenized_documents = [
            self._tokenize(document["content"])
            for document in documents
        ]

        self.document_lengths = [
            len(tokens)
            for tokens in self.tokenized_documents
        ]

        self.avg_document_length = (
            sum(self.document_lengths) / len(self.document_lengths)
            if self.document_lengths
            else 0.0
        )

        self.document_frequency = self._build_document_frequency()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"\b\w+\b", text.lower())

    def _build_document_frequency(self) -> dict[str, int]:
        frequencies: Counter[str] = Counter()

        for tokens in self.tokenized_documents:
            for token in set(tokens):
                frequencies[token] += 1

        return dict(frequencies)

    def _idf(self, term: str) -> float:
        document_count = len(self.documents)
        frequency = self.document_frequency.get(term, 0)

        if document_count == 0 or frequency == 0:
            return 0.0

        return math.log(
            1
            + (document_count - frequency + 0.5)
            / (frequency + 0.5)
        )

    def _score_document(
        self,
        query_terms: list[str],
        document_index: int,
    ) -> float:
        if not self.documents:
            return 0.0

        tokens = self.tokenized_documents[document_index]
        term_frequency = Counter(tokens)
        document_length = self.document_lengths[document_index]

        score = 0.0

        for term in query_terms:
            tf = term_frequency.get(term, 0)

            if tf == 0:
                continue

            idf = self._idf(term)

            denominator = (
                tf
                + self.k1
                * (
                    1
                    - self.b
                    + self.b
                    * (
                        document_length
                        / self.avg_document_length
                    )
                )
            )

            score += idf * (
                (tf * (self.k1 + 1))
                / denominator
            )

        return score

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        query_terms = self._tokenize(query)

        results = []

        for index, document in enumerate(self.documents):
            score = self._score_document(
                query_terms,
                index,
            )

            results.append(
                {
                    **document,
                    "score": score,
                }
            )

        results.sort(
            key=lambda result: result["score"],
            reverse=True,
        )

        return results[:top_k]