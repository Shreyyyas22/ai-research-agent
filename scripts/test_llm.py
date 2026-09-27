import asyncio

from app.llm.groq import GroqProvider

async def main() -> None:
    provider = GroqProvider()

    messages = [
        {
            "role": "system",
            "content": "You are a helpful research assistant."
        },
        {
            "role": "user",
            "content": "Explain RAG in one paragraph."
        },
    ]

    response = await provider.generate(messages)
    print(response)

if __name__ == "__main__":
    asyncio.run(main())