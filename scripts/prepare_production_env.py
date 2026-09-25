import json
import secrets
from pathlib import Path

from pydantic import SecretStr

from backend.app.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / ".env.production"


def reveal(value: SecretStr | None) -> str:
    return value.get_secret_value() if value is not None else ""


def main() -> None:
    settings = Settings(_env_file=PROJECT_ROOT / ".env")
    postgres_password = secrets.token_urlsafe(32)
    values = {
        "APP_NAME": settings.app_name,
        "APP_LOG_LEVEL": settings.app_log_level,
        "CORS_ORIGINS": json.dumps(settings.cors_origins, ensure_ascii=False),
        "POSTGRES_DB": "ai_private_chef",
        "POSTGRES_USER": "chef",
        "POSTGRES_PASSWORD": postgres_password,
        "DASHSCOPE_API_KEY": reveal(settings.dashscope_api_key),
        "DASHSCOPE_BASE_URL": settings.dashscope_base_url,
        "DASHSCOPE_MODEL": settings.dashscope_model,
        "QWEN_REASONING_EFFORT": settings.qwen_reasoning_effort,
        "QWEN_IMAGE_MAX_PIXELS": str(settings.qwen_image_max_pixels),
        "TAVILY_API_KEY": reveal(settings.tavily_api_key),
        "LANGSMITH_API_KEY": reveal(settings.langsmith_api_key),
        "LANGSMITH_TRACING": "true" if settings.langsmith_tracing else "false",
        "LANGSMITH_PROJECT": "ai-private-chef-production",
        "LANGSMITH_HIDE_INPUTS": "true",
        "LANGSMITH_HIDE_OUTPUTS": "true",
        "OSS_REGION": settings.oss_region or "",
        "OSS_ENDPOINT": settings.oss_endpoint or "",
        "OSS_BUCKET": settings.oss_bucket or "",
        "OSS_ACCESS_KEY_ID": reveal(settings.oss_access_key_id),
        "OSS_ACCESS_KEY_SECRET": reveal(settings.oss_access_key_secret),
        "OSS_UPLOAD_URL_TTL_SECONDS": str(settings.oss_upload_url_ttl_seconds),
        "OSS_DOWNLOAD_URL_TTL_SECONDS": str(settings.oss_download_url_ttl_seconds),
        "OSS_MAX_IMAGE_SIZE_BYTES": str(settings.oss_max_image_size_bytes),
    }
    content = "\n".join(f"{key}={value}" for key, value in values.items()) + "\n"
    OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Created {OUTPUT_PATH.name} with a generated PostgreSQL password.")


if __name__ == "__main__":
    main()
