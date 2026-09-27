from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...


    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    async def execute(
        self,
        input: dict[str, Any],
    ) -> dict[str, Any]:
        ...