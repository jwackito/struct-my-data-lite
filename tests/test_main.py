import pytest

from app.config import settings
from app.main import _parse_model_id


@pytest.mark.asyncio
async def test_parse_model_id_empty_returns_default_model():
    result = await _parse_model_id("")
    assert result == ("ollama", "ollama", settings.ollama_model)