"""Application settings — everything comes from the environment (.env supported)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="WB_", extra="ignore"
    )

    app_name: str = "Whiteboard"
    env: str = "development"  # development | test | production
    api_prefix: str = "/api"
    static_dir: str = ""  # path to frontend/dist; served from the same process when set

    # DB
    database_url: str = "sqlite:///./whiteboard.db"
    sql_echo: bool = False

    # Behaviour
    max_doc_bytes: int = 4 * 1024 * 1024  # 4 MB per board document
    max_boards: int = 500

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
