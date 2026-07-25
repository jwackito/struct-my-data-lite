from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

from instructor import Instructor


@dataclass
class ModelInfo:
    id: str
    provider: str
    model_name: str
    capabilities: List[str] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    def get_client(self, model_name: str = "") -> Instructor:
        ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        ...
