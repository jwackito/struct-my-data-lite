import instructor
from openai import OpenAI

from app.config import settings
from app.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str, vision_model: str):
        self.host = host
        self.model = model
        self.vision_model = vision_model

    def get_client(self):
        return instructor.from_openai(
            OpenAI(base_url=f"{self.host}/v1", api_key="ollama", timeout=settings.ollama_timeout),
            mode=instructor.Mode.JSON,
        )
