from collections.abc import Iterable
from typing import Any, Protocol

from groq.types.chat import ChatCompletionMessageParam


class LLMProvider(Protocol):
    async def generate(
        self, messages: Iterable[ChatCompletionMessageParam], **kwargs: Any
    ) -> str: ...

    async def generate_structured(
        self,
        messages: Iterable[ChatCompletionMessageParam],
        response_model: type[Any],
        **kwargs: Any,
    ) -> Any: ...
