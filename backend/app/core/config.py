from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AI Private Chef"
    app_env: Literal["development", "test", "production"] = "development"
    app_debug: bool = False
    app_log_level: str = "INFO"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://127.0.0.1:8000", "http://localhost:8000"]

    database_url: str = "sqlite+aiosqlite:///./data/ai_private_chef.db"
    checkpointer_backend: Literal["sqlite", "postgres"] = "sqlite"
    checkpoint_sqlite_path: Path = Path("./data/checkpoints.sqlite")

    dashscope_api_key: SecretStr | None = None
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_model: str = "qwen3.7-plus"
    qwen_reasoning_effort: Literal["none", "low", "medium", "xhigh"] = "none"
    qwen_image_max_pixels: int = Field(default=8_388_608, ge=3_136, le=819_200_000)
    tavily_api_key: SecretStr | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_tracing: bool = False
    langsmith_project: str = "ai-private-chef-dev"
    langsmith_hide_inputs: bool = True
    langsmith_hide_outputs: bool = True

    oss_region: str | None = None
    oss_endpoint: str | None = None
    oss_bucket: str | None = None
    oss_access_key_id: SecretStr | None = None
    oss_access_key_secret: SecretStr | None = None
    oss_upload_url_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    oss_download_url_ttl_seconds: int = Field(default=300, ge=60, le=3600)
    oss_max_image_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1)

    @field_validator("app_log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        if normalized not in allowed:
            raise ValueError(f"APP_LOG_LEVEL must be one of {sorted(allowed)}")
        return normalized

    @field_validator("dashscope_model", mode="before")
    @classmethod
    def default_dashscope_model(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return "qwen3.7-plus"
        return value

    @property
    def debug(self) -> bool:
        return self.app_debug

    @property
    def log_level(self) -> str:
        return self.app_log_level


@lru_cache
def get_settings() -> Settings:
    return Settings()
