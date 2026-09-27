from typing import Any

class FakeLLMProvider:
    async def generate(self, messages: list[dict[str, str]], **kwargs: Any,) -> str:
        return "This is a fake response"
    
    async def generate_structured(self, messages: list[dict[str, str]], response_model: type[Any], **kwargs: Any,) -> Any:
        raise NotImplementedError