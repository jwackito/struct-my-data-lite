from app.config import settings
from app.providers.base import LLMProvider, ModelInfo
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def get_provider(name: str) -> LLMProvider:
    if name == "ollama":
        return OllamaProvider(settings.ollama_host, settings.ollama_model, settings.ollama_vision_model)
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    raise ValueError(f"Unknown provider: {name}")


def list_all_models() -> list[dict]:
    seen = set()
    results = []
    for name in ("ollama", "openai", "gemini"):
        try:
            provider = get_provider(name)
        except Exception:
            continue
        for model in provider.list_models():
            if model.id in seen:
                continue
            seen.add(model.id)
            if "embeddings" in model.capabilities and len(model.capabilities) == 1:
                continue
            results.append({
                "id": model.id,
                "provider": model.provider,
                "model": model.model_name,
                "capabilities": model.capabilities,
            })
    return results
