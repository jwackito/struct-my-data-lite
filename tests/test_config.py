from app.config import settings


def test_vision_model_default():
    assert settings.ollama_vision_model == "gemma4:31b"
