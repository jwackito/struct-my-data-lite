import urllib.request
import json

import instructor
from openai import OpenAI

from app.config import settings
from app.providers.base import LLMProvider, ModelInfo


class OllamaProvider(LLMProvider):
    def __init__(self, host: str, model: str, vision_model: str):
        self.host = host
        self.model = model
        self.vision_model = vision_model

    def get_client(self, model_name: str = ""):
        return instructor.from_openai(
            OpenAI(base_url=f"{self.host}/v1", api_key="ollama", timeout=settings.ollama_timeout),
            mode=instructor.Mode.JSON,
        )

    def list_models(self) -> list[ModelInfo]:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []

        vision_keywords = {"vision", "llava", "gemma4"}
        results = []
        for m in data.get("models", []):
            name = m["name"]
            name_lower = name.lower()
            if any(k in name_lower for k in vision_keywords):
                caps = ["text", "vision"]
            else:
                caps = ["text"]
            results.append(ModelInfo(
                id=f"ollama/{name}",
                provider="ollama",
                model_name=name,
                capabilities=caps,
            ))
        return results
