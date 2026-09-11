import pytest
from sqlalchemy import select

from app.config import settings
from app.main import _parse_model_id
from app.models import LLMConnection, ModelRegistry


@pytest.mark.asyncio
async def test_parse_model_id_empty_uses_pinned_default(async_client, db_session):
    await db_session.commit()
    pinned = await _parse_model_id("", db_session)
    assert pinned == ("ollama", "ollama", settings.ollama_model)


@pytest.mark.asyncio
async def test_parse_model_id_empty_uses_registry_default_when_pinned(async_client, db_session):
    await db_session.commit()
    reg = ModelRegistry(connection_id=None, model_name="qwen-custom", enabled=True, is_default=True)
    db_session.add(reg)
    await db_session.commit()

    pinned = await _parse_model_id("", db_session)
    assert pinned == ("ollama", "ollama", "qwen-custom")


@pytest.mark.asyncio
async def test_parse_model_id_forms(async_client, db_session):
    assert await _parse_model_id("openai/my-key/gpt-4o", db_session) == ("openai", "my-key", "gpt-4o")
    assert await _parse_model_id("openai/gpt-4o", db_session) == ("openai", "openai", "gpt-4o")
    assert await _parse_model_id("weird", db_session) == ("weird", "weird", None)