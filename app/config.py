"""
Application configuration using Pydantic Settings.
All values are loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Ollama ────────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL of the local Ollama server.",
    )
    ollama_model: str = Field(
        default="qwen3:8b",
        description="Ollama model tag to use for inference.",
    )
    ollama_keep_alive: str = Field(
        default="30m",
        description="How long Ollama should keep the model loaded in memory.",
    )
    ollama_timeout: float = Field(
        default=5.0,
        description="Seconds to wait when health-checking Ollama.",
    )

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key (leave blank when offline-only).",
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash",
        description="Gemini model name.",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./assistant.db",
        description="SQLAlchemy async database URL.",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8000",
        ],
        description="Comma-separated list of allowed CORS origins.",
    )

    # ── Application ───────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO", description="Python logging level.")
    app_title: str = "Offline-First AI Assistant"
    app_version: str = "0.1.0"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings (singleton)."""
    return Settings()
