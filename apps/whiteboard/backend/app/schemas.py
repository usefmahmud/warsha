"""Pydantic schemas — request/response contract for /api/boards."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX = 160
DEFAULT_DOC: dict[str, Any] = {"version": "6.0.0", "objects": [], "background": "#0b1020"}


def to_iso_z(value: datetime | None) -> str | None:
    """Naive UTC → ISO-8601 with an explicit `Z` (matches the Atlas convention)."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_doc(raw: str | None) -> dict[str, Any]:
    if not raw:
        return dict(DEFAULT_DOC)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return dict(DEFAULT_DOC)
    return value if isinstance(value, dict) else dict(DEFAULT_DOC)


class BoardCreate(BaseModel):
    name: str = Field(default="بورد جديد", min_length=1, max_length=NAME_MAX)
    color: str = Field(default="#6366f1", max_length=24)
    doc: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("الاسم مطلوب")
        return v


class BoardUpdate(BaseModel):
    """Partial update. `version` enables optimistic concurrency on autosave."""

    name: str | None = Field(default=None, min_length=1, max_length=NAME_MAX)
    color: str | None = Field(default=None, max_length=24)
    doc: dict[str, Any] | None = None
    thumb: str | None = None
    version: int | None = Field(default=None, ge=0)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("الاسم مطلوب")
        return v


class ShareOut(BaseModel):
    share_token: str
    share_url: str


class BoardOut(BaseModel):
    """Full board including the scene document (used by GET /{id} and PATCH)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str
    doc: dict[str, Any]
    thumb: str | None
    share_token: str | None
    version: int
    created_at: str
    updated_at: str

    @classmethod
    def from_orm_board(cls, board) -> BoardOut:
        return cls(
            id=board.id,
            name=board.name,
            color=board.color,
            doc=parse_doc(board.doc),
            thumb=board.thumb,
            share_token=board.share_token,
            version=board.version,
            created_at=to_iso_z(board.created_at),
            updated_at=to_iso_z(board.updated_at),
        )


class BoardSummary(BaseModel):
    """Lightweight row for the board list (no doc, no thumbnail payload)."""

    id: str
    name: str
    color: str
    version: int
    object_count: int
    has_thumb: bool
    share_token: str | None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm_board(cls, board) -> BoardSummary:
        doc = parse_doc(board.doc)
        objects = doc.get("objects")
        return cls(
            id=board.id,
            name=board.name,
            color=board.color,
            version=board.version,
            object_count=len(objects) if isinstance(objects, list) else 0,
            has_thumb=bool(board.thumb),
            share_token=board.share_token,
            created_at=to_iso_z(board.created_at),
            updated_at=to_iso_z(board.updated_at),
        )
