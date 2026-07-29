import json
import urllib.request

import instructor
from openai import OpenAI

from app.config import settings
from app.providers.base import LLMProvider, ModelInfo


_KNOWN_CAPABILITIES = {
    "gpt-4o": ["text", "vision"],
    "gpt-4o-mini": ["text", "vision"],
    "gpt-4o-audio-preview": ["text", "vision"],
    "gpt-4": ["text"],
    "gpt-4-turbo": ["text", "vision"],
    "gpt-4.1": ["text", "vision"],
    "gpt-4.1-mini": ["text", "vision"],
    "gpt-4.1-nano": ["text"],
    "o1": ["text"],
    "o1-mini": ["text"],
    "o3-mini": ["text"],
    "text-embedding-3-small": ["embeddings"],
    "text-embedding-3-large": ["embeddings"],
    "text-embedding-ada-002": ["embeddings"],
}


_KNWON_FAMILIES = {
    "gpt-4o", "gpt-4", "gpt-4-turbo", "gpt-3.5-turbo",
    "gpt-4.1", "o1", "o3-mini",
    "text-embedding-3", "text-embedding-ada",
}


def _classify(model_id: str) -> list[str]:
    for prefix, caps in _KNOWN_CAPABILITIES.items():
        if model_id.startswith(prefix):
            return list(caps)
    if "embedding" not in model_id.lower():
        return ["text"]
    return []


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url

    def get_client(self, model_name: str = ""):
        kwargs = {"api_key": self.api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        return instructor.from_openai(
            OpenAI(**kwargs),
            mode=instructor.Mode.JSON,
        )

    def list_models(self) -> list[ModelInfo]:
        if not self.api_key:
            return []

        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = self.base_url.rstrip("/") + "/models" if self.base_url else "https://api.openai.com/v1/models"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []

        results = []
        for m in data.get("data", []):
            model_id = m["id"]
            caps = _classify(model_id)
            if not caps:
                continue
            results.append(ModelInfo(
                id=f"openai/{model_id}",
                provider="openai",
                model_name=model_id,
                capabilities=caps,
            ))
        return results
