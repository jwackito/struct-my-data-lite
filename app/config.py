from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/structmydata"
    ollama_host: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3.6:35b"
    max_upload_size: int = 10 * 1024 * 1024
    ollama_timeout: int = 120
    skip_db_wait: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
