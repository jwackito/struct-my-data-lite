import instructor
from openai import OpenAI

from app.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model

    def get_client(self):
        return instructor.from_openai(
            OpenAI(base_url=f"{self.host}/v1", api_key="ollama"),
            mode=instructor.Mode.JSON,
        )
