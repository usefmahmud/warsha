"""ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TodoPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"


PRIORITY_ORDER = {TodoPriority.high: 0, TodoPriority.normal: 1, TodoPriority.low: 2}
PRIORITY_LABELS = {
    TodoPriority.high: "عالية",
    TodoPriority.normal: "عادية",
    TodoPriority.low: "منخفضة",
}


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    priority: Mapped[TodoPriority] = mapped_column(
        Enum(TodoPriority, name="todo_priority", native_enum=False, length=16),
        nullable=False,
        default=TodoPriority.normal,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "notes": self.notes,
            "done": self.done,
            "priority": self.priority.value
            if isinstance(self.priority, TodoPriority)
            else str(self.priority),
            "created_at": _iso(self.created_at),
            "updated_at": _iso(self.updated_at),
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
