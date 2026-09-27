import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.groq import GroqProvider
from tests.fakes import FakeLLMProvider

async def use_provider(provider) -> None:
    messages = [
        {
            "role": "user",
            "content": "What is an AI agent?",
        }
    ]
    response = await provider.generate(messages)

    print(response)

async def main() -> None:
    print("====== Fake Provider ======")

    fake_provider = FakeLLMProvider()
    await use_provider(fake_provider)
    print("\n ===== Groq Provider ======")
    
    groq_provider = GroqProvider()

    await use_provider(groq_provider)

if __name__ == "__main__":
    asyncio.run(main())