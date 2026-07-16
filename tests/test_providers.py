from unittest.mock import patch

import pytest

from app.providers.base import LLMProvider
from app.providers.factory import get_provider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider


def test_factory_ollama():
    provider = get_provider("ollama")
    assert isinstance(provider, OllamaProvider)
    assert "host.docker.internal" in provider.host


def test_factory_openai():
    provider = get_provider("openai")
    assert isinstance(provider, OpenAIProvider)


def test_factory_unknown():
    with pytest.raises(ValueError, match="Unknown"):
        get_provider("unknown")


def test_openai_stub_not_implemented():
    provider = OpenAIProvider()
    with pytest.raises(NotImplementedError):
        provider.get_client()


@patch("app.providers.ollama.OpenAI")
@patch("app.providers.ollama.instructor.from_openai")
def test_ollama_get_client(mock_from_openai, mock_openai):
    provider = OllamaProvider("http://test:11434", "test-model", "vision-model")
    client = provider.get_client()
    mock_openai.assert_called_once_with(base_url="http://test:11434/v1", api_key="ollama", timeout=3600)
    mock_from_openai.assert_called_once()
    assert client == mock_from_openai.return_value


class TestABC:
    def test_cannot_instantiate(self):
        class Incomplete(LLMProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()
