from typing import Any


class ReciprocalRankFusion:
    """Combine ranked retrieval results using Reciprocal Rank Fusion."""

    def __init__(self, k: int = 60) -> None:
        if k <= 0:
            raise ValueError("k must be greater than zero.")

        self.k = k

    def fuse(
        self,
        result_lists: list[list[dict[str, Any]]],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not result_lists:
            return []

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        scores: dict[str, float] = {}
        results_by_id: dict[str, dict[str, Any]] = {}

        for result_list in result_lists:
            for rank, result in enumerate(result_list, start=1):
                result_id = str(result["id"])

                scores[result_id] = scores.get(result_id, 0.0) + (
                    1.0 / (self.k + rank)
                )

                results_by_id[result_id] = result

        ranked_ids = sorted(
            scores,
            key=lambda result_id: scores[result_id],
            reverse=True,
        )

        results = []

        for result_id in ranked_ids[:top_k]:
            result = dict(results_by_id[result_id])
            result["rrf_score"] = scores[result_id]
            results.append(result)

        return results

class HybridRetriever:
    """Combine dense vector retrieval and BM25 using RRF."""

    def __init__(
        self,
        vector_search,
        bm25,
        rrf: ReciprocalRankFusion | None = None,
    ) -> None:
        self.vector_search = vector_search
        self.bm25 = bm25
        self.rrf = rrf or ReciprocalRankFusion()

    async def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        if not query_embedding:
            raise ValueError("Query embedding cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        vector_results = await self.vector_search.search(
            query_embedding=query_embedding,
            top_k=top_k,
        )

        bm25_results = self.bm25.search(
            query=query,
            top_k=top_k,
        )

        return self.rrf.fuse(
            result_lists=[
                vector_results,
                bm25_results,
            ],
            top_k=top_k,
        )