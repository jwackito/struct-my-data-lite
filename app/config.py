from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/structmydata"
    ollama_host: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3.6:35b"
    ollama_vision_model: str = "gemma4:31b"
    max_upload_size: int = 10 * 1024 * 1024
    ollama_timeout: int = 3600
    openai_api_key: str = ""
    openai_base_url: str = ""
    gemini_api_key: str = ""
    app_secret_key: str = ""
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24
    allow_registration: bool = True
    batch_concurrency: int = 2
    max_batch_size: int = 50
    job_queue_max: int = 4
    rate_limit_auth: int = 10
    rate_limit_extract: int = 30
    rate_limit_batch: int = 5
    skip_db_wait: bool = False
    log_level: str = "INFO"
    env: str = "dev"
    per_user_concurrency: int = 1
    daily_job_cap: int = 0
    usage_enforced: bool = False
    billing_enabled: bool = False
    queue_backend: str = "inprocess"
    redis_url: str = ""
    invite_only: bool = False

    class Config:
        env_file = "etc/.env"


settings = Settings()
