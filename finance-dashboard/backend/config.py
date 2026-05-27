"""
backend/config.py

Central settings object. All environment variables are read here — nowhere else.
Using pydantic-settings gives us automatic validation, type coercion, and
a clear audit trail of every config value the app depends on.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Plaid ────────────────────────────────────────────────────
    plaid_client_id: str
    plaid_secret: str
    plaid_env: str = "sandbox"  # sandbox | production

    # ── Encryption ───────────────────────────────────────────────
    encryption_key: str  # Fernet key — generate once and keep in .env

    # ── Database ─────────────────────────────────────────────────
    database_url: str = "sqlite:///./finance.db"

    # ── Server ───────────────────────────────────────────────────
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached singleton — the same Settings instance is reused across the app.
    Call this anywhere you need config:  settings = get_settings()
    """
    return Settings()  # type: ignore[call-arg]
