from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "paper_reader.db"
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "papers"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    dashscope_api_key: SecretStr | None = None
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_translation_model: str = "qwen3.7-plus"
    qwen_analysis_model: str = "qwen3.7-max"
    qwen_chat_model: str = "qwen3.7-max"

    database_url: str = f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
    storage_path: Path = DEFAULT_STORAGE_PATH
    max_pdf_size_mb: int = 100

    @property
    def llm_configured(self) -> bool:
        return bool(self.dashscope_api_key and self.dashscope_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
