"""ORM models — Atlas v1 (PRD §6).

IDs are application-generated UUID4 strings so the same schema ports to Postgres.
Timestamps are naive UTC in SQLite and rendered with a trailing `Z` at the API edge.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class UserRole(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class ProjectRole(str, enum.Enum):
    lead = "lead"
    member = "member"


class TicketType(str, enum.Enum):
    task = "task"
    bug = "bug"
    story = "story"
    chore = "chore"


class TicketPriority(str, enum.Enum):
    urgent = "urgent"
    high = "high"
    normal = "normal"
    low = "low"


class TicketStatus(str, enum.Enum):
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    blocked = "blocked"
    done = "done"


# Board order is fixed by the PRD (AC-16.1); /api/meta exposes it to the frontend.
STATUS_ORDER: tuple[TicketStatus, ...] = (
    TicketStatus.backlog,
    TicketStatus.todo,
    TicketStatus.in_progress,
    TicketStatus.review,
    TicketStatus.blocked,
    TicketStatus.done,
)

STATUS_LABELS = {
    TicketStatus.backlog: "Backlog",
    TicketStatus.todo: "To Do",
    TicketStatus.in_progress: "In Progress",
    TicketStatus.review: "Review",
    TicketStatus.blocked: "Blocked",
    TicketStatus.done: "Done",
}

# PRD §5.1: any state → any state, except done → * which members cannot do.
ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    status: {other for other in TicketStatus if other is not status} for status in TicketStatus
}
MEMBER_FORBIDDEN_TRANSITIONS: set[tuple[TicketStatus, TicketStatus]] = {
    (TicketStatus.done, other) for other in TicketStatus if other is not TicketStatus.done
}

MAX_SUBTASK_DEPTH = 2  # parent + child only (AC-11.2)


def _enum(py_enum, name: str) -> SAEnum:
    return SAEnum(
        py_enum,
        name=name,
        native_enum=False,
        length=20,
        validate_strings=True,
        values_callable=lambda e: [m.value for m in e],
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    color: Mapped[str] = mapped_column(String(9), nullable=False, default="#2563EB")
    role: Mapped[UserRole] = mapped_column(_enum(UserRole, "user_role"), default=UserRole.member)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    memberships: Mapped[list[ProjectMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False, default="agent")
    prefix: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    key: Mapped[str] = mapped_column(String(6), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#2563EB", nullable=False)
    ticket_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    members: Mapped[list[ProjectMember]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    labels: Mapped[list[Label]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_member_project_user"),)

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role_in_project: Mapped[ProjectRole] = mapped_column(
        _enum(ProjectRole, "project_role"), default=ProjectRole.member
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_label_project_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#94A3B8", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="labels")
    ticket_links: Mapped[list[TicketLabel]] = relationship(
        back_populates="label", cascade="all, delete-orphan"
    )


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("project_id", "number", name="uq_ticket_project_number"),
        UniqueConstraint("project_id", "client_ref", name="uq_ticket_project_client_ref"),
        Index("ix_tickets_board", "project_id", "status", "board_position"),
        Index("ix_tickets_assignee_status", "assignee_id", "status"),
        Index("ix_tickets_project_updated", "project_id", "updated_at"),
        Index("ix_tickets_parent", "parent_id"),
        Index("ix_tickets_due", "due_date", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description_md: Mapped[str] = mapped_column(Text, default="", nullable=False)
    type: Mapped[TicketType] = mapped_column(
        _enum(TicketType, "ticket_type"), default=TicketType.task
    )
    priority: Mapped[TicketPriority] = mapped_column(
        _enum(TicketPriority, "ticket_priority"), default=TicketPriority.normal
    )
    status: Mapped[TicketStatus] = mapped_column(
        _enum(TicketStatus, "ticket_status"), default=TicketStatus.backlog, index=True
    )
    blocked_reason: Mapped[str | None] = mapped_column(String(500))
    assignee_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="SET NULL"))
    due_date: Mapped[date | None] = mapped_column(Date)
    estimate_points: Mapped[int | None] = mapped_column(Integer)
    board_position: Mapped[float] = mapped_column(Float, default=1024.0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    client_ref: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    project: Mapped[Project] = relationship(back_populates="tickets")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id])
    reporter: Mapped[User] = relationship(foreign_keys=[reporter_id])
    parent: Mapped[Ticket | None] = relationship(
        remote_side=[id], back_populates="children", foreign_keys=[parent_id]
    )
    children: Mapped[list[Ticket]] = relationship(
        back_populates="parent", foreign_keys=[parent_id]
    )
    comments: Mapped[list[Comment]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    label_links: Mapped[list[TicketLabel]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )
    attachments: Mapped[list[Attachment]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )


class TicketLabel(Base):
    __tablename__ = "ticket_labels"

    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[str] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True, index=True
    )

    ticket: Mapped[Ticket] = relationship(back_populates="label_links")
    label: Mapped[Label] = relationship(back_populates="ticket_links")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="comments")
    author: Mapped[User] = relationship()


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("comment_id", "mentioned_user_id", name="uq_mention_comment_user"),
        Index("ix_mentions_user_created", "mentioned_user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    comment_id: Mapped[str | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"))
    mentioned_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped[User] = relationship()


class Activity(Base):
    __tablename__ = "activity"
    __table_args__ = (Index("ix_activity_ticket_created", "ticket_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    field: Mapped[str | None] = mapped_column(String(40))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(40), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship()
    ticket: Mapped[Ticket | None] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_read", "user_id", "read_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey("tickets.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False, index=True
    )

    actor: Mapped[User | None] = relationship(foreign_keys=[actor_id])
    ticket: Mapped[Ticket | None] = relationship()


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(16), default="link", nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    ticket: Mapped[Ticket] = relationship(back_populates="attachments")


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_status: Mapped[int | None] = mapped_column(Integer)
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
