import json
import urllib.parse
import urllib.request

import instructor

from app.config import settings
from app.providers.base import LLMProvider, ModelInfo


_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1"


def _classify_gemini(model_dict: dict) -> list[str]:
    name = model_dict.get("name", "")
    methods = model_dict.get("supportedGenerationMethods", [])

    has_generate = "generateContent" in methods
    has_embed = "embedContent" in methods

    if has_generate and has_embed:
        return ["text", "vision"]
    if has_generate:
        return ["text", "vision"]
    if has_embed:
        return ["embeddings"]
    return []


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or settings.gemini_api_key
        self._default_model = model

    def get_client(self, model_name: str = ""):
        import google.generativeai as genai

        genai.configure(api_key=self.api_key)
        client = genai.GenerativeModel(model_name=model_name or self._default_model)
        return instructor.from_gemini(
            client=client,
            mode=instructor.Mode.GEMINI_JSON,
        )

    def list_models(self) -> list[ModelInfo]:
        if not self.api_key:
            return []

        params = urllib.parse.urlencode({"key": self.api_key})
        url = f"{_GEMINI_API_BASE}/models?{params}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
        except Exception:
            return []

        results = []
        for m in data.get("models", []):
            raw_name = m.get("name", "")
            display_name = raw_name.replace("models/", "", 1)
            caps = _classify_gemini(m)
            if not caps:
                continue
            results.append(ModelInfo(
                id=f"gemini/{display_name}",
                provider="gemini",
                model_name=display_name,
                capabilities=caps,
            ))
        return results
