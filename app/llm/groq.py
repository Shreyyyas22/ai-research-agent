import os
from typing import Any, cast

from dotenv import load_dotenv
from groq import AsyncGroq
from pydantic import BaseModel, ValidationError


load_dotenv()


class GroqProvider:

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "openai/gpt-oss-20b",
    ) -> None:

        api_key = api_key or os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Add it to your .env file."
            )

        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:

        request: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **kwargs,
        }

        response = await self.client.chat.completions.create(
            **cast(Any, request)
        )

        return response.choices[0].message.content or ""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
    ) -> Any:

        schema = response_model.model_json_schema()

        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "strict": True,
                "schema": schema,
            },
        }

        request_messages = list(messages)

        for attempt in range(2):

            request: dict[str, Any] = {
                "model": self.model,
                "messages": request_messages,
                "response_format": response_format,
            }

            response = await self.client.chat.completions.create(
                **cast(Any, request)
            )

            content = response.choices[0].message.content or ""

            try:
                return response_model.model_validate_json(content)

            except ValidationError as exc:

                if attempt == 1:
                    raise

                request_messages.append(
                    {
                        "role": "user",
                        "content": (
                            "The previous response failed schema "
                            "validation. Return a corrected response "
                            "that strictly matches the required schema.\n\n"
                            f"Validation error:\n{exc}"
                        ),
                    }
                )