import asyncio

from app.agents.graph import build_research_graph


async def main() -> None:
    graph = build_research_graph()

    initial_state = {
        "question": "Should a high-traffic SaaS application use PostgreSQL or MongoDB?"
    }

    print("Starting research graph...\n")

    final_state = await graph.ainvoke(initial_state)

    print("\nResearch graph completed.")
    print("\nFinal state:")
    print(final_state)


if __name__ == "__main__":
    asyncio.run(main())