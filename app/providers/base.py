from abc import ABC, abstractmethod

from instructor import Instructor


class LLMProvider(ABC):
    @abstractmethod
    def get_client(self) -> Instructor:
        ...
