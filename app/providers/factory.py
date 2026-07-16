from app.config import settings
from app.providers.base import LLMProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def get_provider(name: str) -> LLMProvider:
    if name == "ollama":
        return OllamaProvider(settings.ollama_host, settings.ollama_model, settings.ollama_vision_model)
    if name == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unknown provider: {name}")
