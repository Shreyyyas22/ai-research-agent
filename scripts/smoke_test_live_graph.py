import asyncio
import json
from uuid import uuid4

from app.agents.production_factory import build_production_research_graph
from app.db.redis import RedisJobStore
from app.services.progress_publisher import ResearchProgressPublisher


async def main():
    research_id = str(uuid4())
    job_store = RedisJobStore.from_env()

    try:
        graph = build_production_research_graph(
            research_id=research_id,
            job_store=job_store,
        )

        result = await graph.ainvoke({
            "question": "What is pgvector HNSW indexing?"
        })

        report = result.get("report")
        evaluation = result.get("report_evaluation")

        if report is None:
            raise RuntimeError("Graph completed without producing a report")

        if evaluation is None:
            raise RuntimeError("Graph completed without producing a report evaluation")

        if hasattr(report, "model_dump"):
            report_data = report.model_dump(mode="json")
        else:
            report_data = report

        if hasattr(evaluation, "model_dump"):
            evaluation_data = evaluation.model_dump(mode="json")
        else:
            evaluation_data = evaluation

        print(json.dumps({
            "status": "PASS",
            "research_id": research_id,
            "report_title": report_data.get("title"),
            "key_findings_count": len(report_data.get("key_findings", [])),
            "sources_count": len(report_data.get("sources", [])),
            "evaluation_score": evaluation_data.get("score"),
            "grounded": evaluation_data.get("grounded"),
            "citation_correct": evaluation_data.get("citation_correct"),
            "hallucination_detected": evaluation_data.get("hallucination_detected"),
            "elapsed_seconds": result.get("elapsed_seconds"),
            "usage_metadata": result.get("usage_metadata"),
        }, indent=2, default=str))

    finally:
        await job_store.client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
