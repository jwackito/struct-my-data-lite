from app.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def get_client(self):
        raise NotImplementedError("OpenAI provider not yet implemented")
