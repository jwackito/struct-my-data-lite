from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.providers.base import LLMProvider
from app.providers.factory import get_provider, list_all_models
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider, _classify
from app.providers.gemini import GeminiProvider


@pytest.mark.asyncio
async def test_factory_ollama():
    provider = await get_provider("ollama", AsyncMock())
    assert isinstance(provider, OllamaProvider)
    assert "host.docker.internal" in provider.host


@pytest.mark.asyncio
@patch("app.providers.factory.get_connection")
async def test_factory_openai(mock_get_conn):
    mock_get_conn.return_value = {
        "name": "my-openai",
        "provider": "openai",
        "config": {"api_key": "sk-test", "base_url": ""},
    }
    provider = await get_provider("my-openai", AsyncMock())
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.asyncio
@patch("app.providers.factory.get_connection")
async def test_factory_unknown(mock_get_conn):
    mock_get_conn.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await get_provider("nonexistent", AsyncMock())


@patch("app.providers.openai.OpenAI")
@patch("app.providers.openai.instructor.from_openai")
def test_openai_get_client(mock_from_openai, mock_openai):
    provider = OpenAIProvider(api_key="test-key")
    client = provider.get_client(model_name="gpt-4o-mini")
    mock_openai.assert_called_once_with(api_key="test-key")
    mock_from_openai.assert_called_once()
    assert client == mock_from_openai.return_value


@patch("app.providers.openai.urllib.request.urlopen")
def test_openai_list_models(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"data":[{"id":"gpt-4o-mini"},{"id":"gpt-4o"},{"id":"text-embedding-3-small"},{"id":"babbage-002"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OpenAIProvider(api_key="test-key")
    models = provider.list_models()
    ids = [m.id for m in models]
    caps = {m.id: m.capabilities for m in models}
    assert "openai/gpt-4o-mini" in ids
    assert "openai/gpt-4o" in ids
    assert "openai/text-embedding-3-small" in ids
    assert caps["openai/text-embedding-3-small"] == ["embeddings"]
    assert "openai/babbage-002" in ids
    assert caps["openai/babbage-002"] == ["text"]


@patch("app.providers.ollama.OpenAI")
@patch("app.providers.ollama.instructor.from_openai")
def test_ollama_get_client(mock_from_openai, mock_openai):
    provider = OllamaProvider("http://test:11434", "test-model", "vision-model")
    client = provider.get_client()
    mock_openai.assert_called_once_with(base_url="http://test:11434/v1", api_key="ollama", timeout=3600)
    mock_from_openai.assert_called_once()
    assert client == mock_from_openai.return_value


@patch("app.providers.ollama.urllib.request.urlopen")
def test_ollama_list_models(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"models":[{"name":"qwen3.6:35b"},{"name":"gemma4:31b"},{"name":"nomic-embed-text"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = OllamaProvider("http://test:11434", "qwen3.6:35b", "gemma4:31b")
    models = provider.list_models()
    ids = [m.id for m in models]
    caps = {m.id: m.capabilities for m in models}
    assert "ollama/qwen3.6:35b" in ids
    assert "ollama/gemma4:31b" in ids
    assert caps["ollama/qwen3.6:35b"] == ["text"]
    assert caps["ollama/gemma4:31b"] == ["text", "vision"]


@patch("app.providers.gemini.urllib.request.urlopen")
def test_gemini_list_models(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"models":[{"name":"models/gemini-2.0-flash","supportedGenerationMethods":["generateContent"]},{"name":"models/gemini-embedding-exp","supportedGenerationMethods":["embedContent"]}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    provider = GeminiProvider(api_key="test-key")
    models = provider.list_models()
    ids = [m.id for m in models]
    caps = {m.id: m.capabilities for m in models}
    assert "gemini/gemini-2.0-flash" in ids
    assert "gemini/gemini-embedding-exp" in ids
    assert caps["gemini/gemini-2.0-flash"] == ["text", "vision"]
    assert caps["gemini/gemini-embedding-exp"] == ["embeddings"]


@pytest.mark.asyncio
@patch("app.providers.factory._build_provider")
@patch("app.providers.factory.get_connection")
@patch("app.providers.factory.list_connections")
async def test_list_all_models_filters_embeddings(mock_list_conn, mock_get_conn, mock_build_provider):
    from app.providers.base import ModelInfo

    mock_list_conn.return_value = [
        {"name": "ollama", "provider": "ollama", "config": {"host": "http://test:11434"}, "enabled": True},
        {"name": "my-openai", "provider": "openai", "config": {"api_key": "****sk-test"}, "enabled": True},
    ]
    mock_get_conn.side_effect = [
        {"name": "ollama", "provider": "ollama", "config": {"host": "http://test:11434"}},
        {"name": "my-openai", "provider": "openai", "config": {"api_key": "sk-test-secret", "base_url": ""}},
    ]

    ollama_provider = MagicMock()
    ollama_provider.list_models.return_value = [ModelInfo(id="ollama/qwen3.6:35b", provider="ollama", model_name="qwen3.6:35b", capabilities=["text"])]
    openai_provider = MagicMock()
    openai_provider.list_models.return_value = [
        ModelInfo(id="openai/gpt-4o-mini", provider="openai", model_name="gpt-4o-mini", capabilities=["text", "vision"]),
        ModelInfo(id="openai/text-embedding-3-small", provider="openai", model_name="text-embedding-3-small", capabilities=["embeddings"]),
    ]

    def build_side_effect(provider, config):
        if provider == "ollama":
            return ollama_provider
        return openai_provider
    mock_build_provider.side_effect = build_side_effect

    result = await list_all_models(AsyncMock())
    ids = [m["id"] for m in result]
    assert "ollama/ollama/qwen3.6:35b" in ids
    assert "openai/my-openai/gpt-4o-mini" in ids
    assert "openai/my-openai/text-embedding-3-small" not in ids
    openai_build_call = [c for c in mock_build_provider.call_args_list if c[0][0] == "openai"][0]
    assert openai_build_call[0][1]["api_key"] == "sk-test-secret"


def test_classify_unknown_model_defaults_to_text():
    assert _classify("llama-3.1-70b") == ["text"]


class TestABC:
    def test_cannot_instantiate(self):
        class Incomplete(LLMProvider):
            pass

        with pytest.raises(TypeError):
            Incomplete()
