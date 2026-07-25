from sqlalchemy.ext.asyncio import AsyncSession

from app.connections import get_connection, list_connections
from app.config import settings
from app.providers.base import LLMProvider, ModelInfo
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def _build_provider(provider: str, config: dict) -> LLMProvider:
    if provider == "ollama":
        return OllamaProvider(
            host=config.get("host", settings.ollama_host),
            model=config.get("model", settings.ollama_model),
            vision_model=config.get("vision_model", settings.ollama_vision_model),
        )
    if provider == "openai":
        return OpenAIProvider(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url", ""),
        )
    if provider == "gemini":
        return GeminiProvider(
            api_key=config.get("api_key", ""),
            model=config.get("model", ""),
        )
    raise ValueError(f"Unknown provider: {provider}")


async def get_provider(connection: str, db: AsyncSession) -> LLMProvider:
    conn = await get_connection(connection, db)
    if not conn:
        raise ValueError(f"Provider connection '{connection}' not found")
    return _build_provider(conn["provider"], conn["config"])


async def list_all_models(db: AsyncSession) -> list[dict]:
    connections = await list_connections(db)
    seen = set()
    results = []

    for conn in connections:
        if not conn["enabled"]:
            continue
        full = await get_connection(conn["name"], db)
        if not full:
            continue
        try:
            provider = _build_provider(full["provider"], full["config"])
        except Exception:
            continue

        for model in provider.list_models():
            model_id = f"{conn['provider']}/{conn['name']}/{model.model_name}"
            if model_id in seen:
                continue
            seen.add(model_id)
            if "embeddings" in model.capabilities and len(model.capabilities) == 1:
                continue
            results.append({
                "id": model_id,
                "provider": conn["provider"],
                "connection": conn["name"],
                "model": model.model_name,
                "capabilities": model.capabilities,
            })

    return results
