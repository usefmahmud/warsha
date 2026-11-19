"""Application settings — environment driven (prefix TODO_)."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_prefix="TODO_", extra="ignore"
    )

    app_name: str = "TODO"
    env: str = "development"
    api_prefix: str = "/api"
    static_dir: str = ""  # path to frontend/dist when served from this process

    database_url: str = "sqlite:///./todo.db"
    sql_echo: bool = False

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
