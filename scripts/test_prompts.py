# import asyncio
# from email import message

# from app.llm.groq import GroqProvider
# from app.prompts.planner import PLANNER_SYSTEM_PROMPT

# async def main() -> None:
#     provider = GroqProvider()

#     messages = [
#         {
#             "role": "system",
#             "content": PLANNER_SYSTEM_PROMPT,
#         },
#         {
#             "role": "user",
#             "content": """
#             Should an e-commerce company use PostgreSQL or MongoDB?
#             """,
#         },
#     ]

#     response = await provider.generate(messages)

#     print(response)

# if __name__ == "__main__":
#     asyncio.run(main())

# import asyncio

# from app.llm.groq import GroqProvider
# from app.prompts.synthesizer import SYNTHESIZER_SYSTEM_PROMPT


# async def main() -> None:
#     provider = GroqProvider()

#     messages = [
#         {
#             "role": "system",
#             "content": SYNTHESIZER_SYSTEM_PROMPT,
#         },
#         {
#             "role": "user",
#             "content": """
# Research question:
# Should an e-commerce company use PostgreSQL or MongoDB?

# Evidence:

# [Source 1]
# PostgreSQL is a relational database that supports
# transactions and complex SQL queries.

# [Source 2]
# MongoDB is a document database that stores data
# in flexible document structures.

# [Source 3]
# MongoDB supports horizontal scaling through sharding.

# Write a short research synthesis based ONLY on
# the evidence provided.
# """,
#         },
#     ]

#     response = await provider.generate(messages)

#     print(response)


# if __name__ == "__main__":
#     asyncio.run(main())


import asyncio

from app.llm.groq import GroqProvider
from app.prompts.evaluator import EVALUATOR_SYSTEM_PROMPT


async def main() -> None:
    provider = GroqProvider()

    messages = [
        {
            "role": "system",
            "content": EVALUATOR_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": """
Research question:
Should an e-commerce company use PostgreSQL or MongoDB?

Evidence:

[Source 1]
PostgreSQL supports transactions and complex SQL queries.

[Source 2]
MongoDB stores data in flexible document structures.

Draft report:

PostgreSQL is always faster than MongoDB.
PostgreSQL is better for every e-commerce company.
MongoDB cannot scale horizontally.
PostgreSQL costs exactly 50% less to operate.

Evaluate this report against the evidence.
Identify unsupported claims.
""",
        },
    ]

    response = await provider.generate(messages)

    print(response)


if __name__ == "__main__":
    asyncio.run(main())