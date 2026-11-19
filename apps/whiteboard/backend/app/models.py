"""ORM models — Whiteboard v1.

IDs are application-generated UUID4 strings so the same schema ports to Postgres.
Timestamps are naive UTC in SQLite and rendered with a trailing `Z` at the API edge.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Board(Base):
    """A whiteboard document: metadata + the Fabric.js JSON scene as text."""

    __tablename__ = "boards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    color: Mapped[str] = mapped_column(String(24), nullable=False, default="#6366f1")
    # Scene document. Stored as TEXT (not JSON) so any client-side canvas library
    # can round-trip it byte-for-byte; validated as JSON at the API edge.
    doc: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # Optional PNG thumbnail as a data URL (client-generated, small).
    thumb: Mapped[str | None] = mapped_column(Text, nullable=True)
    share_token: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=utcnow, onupdate=utcnow
    )
