"""Application settings — everything comes from the environment (.env supported)."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="ATLAS_", extra="ignore"
    )

    app_name: str = "Atlas"
    env: str = "development"  # development | test | production
    api_prefix: str = "/api"
    static_dir: str = ""  # يحدد مسار frontend/dist عند التقديم من نفس العملية

    # Auth — MUST be provided in production; generated ephemeral in dev so no secret lives in code.
    secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12  # PRD Q2 default: 12h, no refresh in v1

    # DB
    database_url: str = "sqlite:///./atlas.db"
    sql_echo: bool = False

    # Behaviour
    allow_registration: bool = True
    allow_private_webhooks: bool = False  # AC-21.4 SSRF guard override
    rate_limit_per_minute: int = 300
    login_attempts_per_minute: int = 5

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173", "http://127.0.0.1:5173"
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def ensure_secret(self) -> None:
        if not self.secret_key:
            if self.env == "production":
                raise RuntimeError("ATLAS_SECRET_KEY is required when ATLAS_ENV=production")
            self.secret_key = secrets.token_urlsafe(48)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_secret()
    return s


settings = get_settings()
