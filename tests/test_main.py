from app.main import _parse_model_id
from app.config import settings


def test_parse_model_id_empty_returns_default_model():
    result = _parse_model_id("")
    assert result == ("ollama", "ollama", settings.ollama_model)
