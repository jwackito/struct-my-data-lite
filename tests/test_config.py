from app.config import Settings, settings


def test_vision_model_default():
    assert settings.ollama_vision_model == "gemma4:31b"


def test_log_level_default():
    assert Settings().log_level == "INFO"


def test_tenant_isolation_defaults():
    s = Settings()
    assert s.env == "dev"
    assert s.per_user_concurrency == 1
    assert s.daily_job_cap == 0
    assert s.usage_enforced is False


def test_saas_config_defaults():
    s = Settings()
    assert s.billing_enabled is False
    assert s.queue_backend == "inprocess"
    assert s.redis_url == ""
    assert s.invite_only is False
    assert s.worker_max_jobs == 4


def test_smtp_config_defaults():
    s = Settings()
    assert s.public_base_url == ""
    assert s.smtp_host == ""
    assert s.smtp_port == 587
    assert s.smtp_username == ""
    assert s.smtp_password == ""
    assert s.smtp_from == ""
    assert s.smtp_starttls is True
