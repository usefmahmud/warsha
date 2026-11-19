"""Pydantic request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Priority = Literal["low", "normal", "high"]


def _clean_title(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("title must be a string")
    value = value.strip()
    if not value:
        raise ValueError("title must not be empty")
    if len(value) > 200:
        raise ValueError("title must be at most 200 characters")
    return value


class TodoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    priority: Priority = "normal"
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str) -> str:
        return _clean_title(v)


class TodoUpdate(BaseModel):
    """PATCH — every field optional, but at least one must be sent."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=5000)
    done: bool | None = None
    priority: Priority | None = None
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, v: str | None) -> str | None:
        return None if v is None else _clean_title(v)


class TodoOut(BaseModel):
    id: str
    title: str
    notes: str | None
    done: bool
    priority: Priority
    created_at: datetime
    updated_at: datetime
    due_date: date | None = None


class TodoListOut(BaseModel):
    items: list[TodoOut]
    count: int
    open_count: int
    done_count: int


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    db: str
    time: datetime
