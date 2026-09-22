from app.config import Settings, settings


def test_vision_model_default():
    assert settings.ollama_vision_model == "gemma4:31b"


def test_log_level_default():
    assert Settings().log_level == "INFO"
