"""Runtime config — env-driven."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="JOB_COPILOT_", extra="ignore")

    # Auth — Supabase JWT (Dashboard → Project Settings → API → JWT Secret).
    # If empty, falls back to dev_token for local development and tests.
    supabase_jwt_secret: str = ""
    dev_token: str = "dev-token"

    # HTTP
    log_level: str = "INFO"

    # LLM — cloud providers only (openai | anthropic).
    # Default model is gpt-4o-mini: fast, cheap, accurate enough for structured extraction.
    llm_provider: Literal["openai", "anthropic"] = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.0
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Storage — set to postgresql+asyncpg://... in production (Supabase pooler URL).
    # Falls back to local SQLite so `pytest` works without any cloud infra.
    database_url: str = (
        "sqlite+aiosqlite:///" + (_BACKEND_DIR / "data" / "jobcopilot.db").as_posix()
    )
    data_dir: Path = _BACKEND_DIR / "data"

    # Mapping
    fuzzy_threshold: int = 82

    # Embeddings (Phase 5)
    embedding_model: str = "text-embedding-3-small"


settings = Settings()

# Create the data dir only for SQLite; Postgres doesn't need a local directory.
if "sqlite" in settings.database_url:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
