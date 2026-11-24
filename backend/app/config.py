"""Application configuration powered by pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings configurable via environment variables or .env."""

    model_config = SettingsConfigDict(
        env_prefix="NG_",
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "NaskahGuard"
    APP_VERSION: str = "0.1.0"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'data' / 'naskahguard.db').as_posix()}"
    STORAGE_DIR: str = str(BASE_DIR / "data" / "storage")
    MAX_UPLOAD_MB: int = 50

    API_TOKEN: str = ""
    RATE_LIMIT_PER_MIN: int = 30
    RETENTION_DAYS: int = 0
    WORKER_THREADS: int = 2

    PDF_BACKEND: Literal["pymupdf", "pypdf"] = "pymupdf"
    OCR_ENABLED: bool = True
    TESSERACT_CMD: str = ""

    SEMANTIC_ENABLED: bool = False
    SEMANTIC_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"

    CONTACT_EMAIL: str = "naskahguard@localhost.localdomain"
    ENABLE_PGVECTOR: bool = False
    NOPLAG_ENGINE_URL: str = ""

    REPORT_PREFIX: str = "NG"
    THRESHOLD_LOW: float = 15.0
    THRESHOLD_HIGH: float = 30.0

    # Phase 7: External Search, Crawler & Acquisition settings
    SEARXNG_URL: str = ""
    WEB_SEARCH_API_URL: str = ""
    WEB_SEARCH_API_KEY: str = ""
    OPENALEX_API_KEY: str = ""
    DEFAULT_MAX_SEARCH_QUERIES: int = 8
    DEFAULT_MAX_CRAWL_URLS: int = 12
    MAX_EXTERNAL_DOWNLOAD_MB: int = 25
    CRAWL_TIMEOUT_SEC: int = 20
    CRAWL_DOMAIN_DELAY_SEC: float = 1.5
    PLAYWRIGHT_ENABLED: bool = True

    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )

    @field_validator("MAX_UPLOAD_MB")
    @classmethod
    def _validate_upload_mb(cls, v: int) -> int:
        if v < 1 or v > 500:
            raise ValueError("MAX_UPLOAD_MB must be between 1 and 500")
        return v

    @property
    def storage_path(self) -> Path:
        return Path(self.STORAGE_DIR).resolve()

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
